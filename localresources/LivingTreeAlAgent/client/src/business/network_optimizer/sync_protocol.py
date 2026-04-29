"""
Merkle Tree Based Incremental Sync Protocol

增量同步协议
- Merkle树构建与比较
- 分块传输
- 冲突解决
- 断点续传
"""

import asyncio
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .models import SyncChunk, MerkleNode


@dataclass
class MerkleSyncProtocol:
    """
    Merkle树增量同步协议
    
    Features:
    - Merkle tree construction
    - Incremental diff calculation
    - Chunked transfer
    - Conflict resolution
    - Resume support
    """
    
    node_id: str
    chunk_size: int = 64 * 1024  # 64KB chunks
    
    # 传输状态: {file_path: {'sent': set, 'total': int}}
    _transfer_state: dict = field(default_factory=dict)
    
    # 待发送队列: list[SyncChunk]
    _pending_chunks: list = field(default_factory=list)
    
    async def incremental_sync(
        self,
        local_files: dict[str, bytes],
        peers: list[str],
        connection_pool,
    ) -> dict:
        """
        增量同步到多个节点
        
        Args:
            local_files: {file_path: content}
            peers: 目标节点列表
            connection_pool: 连接池
            
        Returns:
            dict: 同步结果统计
        """
        results = {
            "files_processed": 0,
            "chunks_sent": 0,
            "bytes_sent": 0,
            "failed_peers": [],
        }
        
        for file_path, content in local_files.items():
            # 1. 构建Merkle树
            local_tree = await self._build_merkle_tree(content)
            local_root = local_tree.hash
            
            # 2. 获取远程Merkle根
            remote_root = await self._get_remote_root(file_path, peers, connection_pool)
            
            # 3. 如果根相同，跳过
            if remote_root == local_root:
                continue
            
            # 4. 计算差异
            diff = await self._calculate_diff(local_tree, remote_root)
            
            # 5. 发送差异块
            for peer_id in peers:
                conn = await connection_pool.get_connection(peer_id)
                if not conn:
                    results["failed_peers"].append(peer_id)
                    continue
                
                for chunk in diff:
                    success = await self._send_chunk(conn, file_path, chunk)
                    if success:
                        results["chunks_sent"] += 1
                        results["bytes_sent"] += chunk.size
            
            results["files_processed"] += 1
        
        return results
    
    async def full_sync(
        self,
        local_files: dict[str, bytes],
        peers: list[str],
        connection_pool,
    ) -> dict:
        """
        全量同步
        
        Args:
            local_files: {file_path: content}
            peers: 目标节点列表
            connection_pool: 连接池
            
        Returns:
            dict: 同步结果
        """
        results = {
            "files_sent": 0,
            "bytes_sent": 0,
            "failed_peers": [],
        }
        
        for file_path, content in local_files.items():
            # 分块
            chunks = await self._chunk_data(content)
            
            # 发送到每个节点
            for peer_id in peers:
                conn = await connection_pool.get_connection(peer_id)
                if not conn:
                    results["failed_peers"].append(peer_id)
                    continue
                
                for chunk in chunks:
                    success = await self._send_chunk(conn, file_path, chunk)
                    if success:
                        results["bytes_sent"] += chunk.size
                
                results["files_sent"] += 1
        
        return results
    
    async def _build_merkle_tree(self, data: bytes) -> MerkleNode:
        """
        构建Merkle树
        
        Args:
            data: 数据内容
            
        Returns:
            MerkleNode: Merkle树根节点
        """
        # 分块
        chunks = await self._chunk_data(data)
        
        # 构建叶子节点
        leaf_nodes = []
        for chunk in chunks:
            chunk_hash = hashlib.sha256(chunk.content).hexdigest()
            leaf = MerkleNode(
                hash=chunk_hash,
                is_leaf=True,
                data=chunk.content,
            )
            leaf_nodes.append(leaf)
        
        # 两两合并构建父节点
        while len(leaf_nodes) > 1:
            new_level = []
            for i in range(0, len(leaf_nodes), 2):
                left = leaf_nodes[i]
                right = leaf_nodes[i + 1] if i + 1 < len(leaf_nodes) else left
                
                combined_hash = hashlib.sha256(
                    (left.hash + right.hash).encode()
                ).hexdigest()
                
                parent = MerkleNode(
                    hash=combined_hash,
                    left=left,
                    right=right,
                )
                new_level.append(parent)
            
            leaf_nodes = new_level
        
        return leaf_nodes[0] if leaf_nodes else MerkleNode(hash="")
    
    async def _chunk_data(self, data: bytes) -> list[SyncChunk]:
        """将数据分块"""
        chunks = []
        for i in range(0, len(data), self.chunk_size):
            chunk_data = data[i:i + self.chunk_size]
            chunk_id = hashlib.sha256(chunk_data).hexdigest()[:16]
            chunks.append(SyncChunk(
                chunk_id=chunk_id,
                content=chunk_data,
                hash=chunk_id,
                offset=i,
                size=len(chunk_data),
            ))
        return chunks
    
    async def _get_remote_root(
        self,
        file_path: str,
        peers: list[str],
        connection_pool,
    ) -> Optional[str]:
        """获取远程Merkle根"""
        for peer_id in peers:
            conn = await connection_pool.get_connection(peer_id)
            if not conn:
                continue
            
            try:
                # 发送Merkle根请求
                request = json.dumps({
                    "type": "merkle_root",
                    "file_path": file_path,
                }).encode()
                await conn.send(request)
                
                # 接收响应
                response = await conn.receive()
                if response:
                    data = json.loads(response)
                    return data.get("root_hash")
            except Exception:
                continue
        
        return None
    
    async def _calculate_diff(
        self,
        local_tree: MerkleNode,
        remote_tree: MerkleNode,
    ) -> list[SyncChunk]:
        """
        计算Merkle树差异
        
        Args:
            local_tree: 本地Merkle树
            remote_tree: 远程Merkle树
            
        Returns:
            list[SyncChunk]: 需要传输的差异块
        """
        diff = []
        await self._tree_diff(local_tree, remote_tree, diff)
        return diff
    
    async def _tree_diff(
        self,
        local: MerkleNode,
        remote: MerkleNode,
        diff: list,
    ):
        """递归比较Merkle树"""
        if local.hash == remote.hash:
            return  # 无差异
        
        if local.is_leaf and remote.is_leaf:
            # 叶子节点不同，添加差异块
            if local.data:
                diff.append(SyncChunk(
                    chunk_id=local.hash[:16],
                    content=local.data,
                    hash=local.hash,
                    size=len(local.data) if local.data else 0,
                ))
            return
        
        # 递归比较子节点
        if local.left and remote.left:
            await self._tree_diff(local.left, remote.left, diff)
        if local.right and remote.right:
            await self._tree_diff(local.right, remote.right, diff)
    
    async def _send_chunk(
        self,
        conn,
        file_path: str,
        chunk: SyncChunk,
    ) -> bool:
        """发送单个块"""
        try:
            # 构建消息
            message = json.dumps({
                "type": "sync_chunk",
                "file_path": file_path,
                "chunk_id": chunk.chunk_id,
                "offset": chunk.offset,
                "size": chunk.size,
                "data": chunk.content.hex() if chunk.content else "",
            }).encode()
            
            # 发送
            return await conn.send(message)
        except Exception:
            return False
    
    async def receive_chunk(self, message: dict) -> bool:
        """
        接收同步块
        
        Args:
            message: 接收到的消息
            
        Returns:
            bool: 是否接收成功
        """
        try:
            file_path = message.get("file_path")
            chunk_id = message.get("chunk_id")
            offset = message.get("offset", 0)
            size = message.get("size", 0)
            data_hex = message.get("data", "")
            
            # 解码数据
            data = bytes.fromhex(data_hex) if data_hex else b""
            
            # 存储到本地
            if file_path not in self._transfer_state:
                self._transfer_state[file_path] = {
                    "chunks": {},
                    "total": size,
                }
            
            self._transfer_state[file_path]["chunks"][offset] = data
            
            return True
        except Exception:
            return False
    
    def get_transfer_state(self, file_path: str) -> dict:
        """获取传输状态"""
        state = self._transfer_state.get(file_path, {})
        if not state:
            return {"progress": 0, "complete": False}
        
        received = sum(len(c) for c in state.get("chunks", {}).values())
        total = state.get("total", 1)
        
        return {
            "progress": received / total if total > 0 else 0,
            "bytes_received": received,
            "total_bytes": total,
            "complete": received >= total,
        }
    
    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "pending_chunks": len(self._pending_chunks),
            "active_transfers": len(self._transfer_state),
            "chunk_size": self.chunk_size,
        }
