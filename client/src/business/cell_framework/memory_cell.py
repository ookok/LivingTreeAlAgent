"""
记忆细胞模块

包含：
- MemoryCell: 通用记忆细胞
- HippocampusCell: 海马体细胞（短期记忆）
- NeocortexCell: 新皮层细胞（长期记忆/知识图谱）
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
from collections import OrderedDict
import json
from .cell import Cell, CellType


class MemoryType(Enum):
    """记忆类型"""
    SHORT_TERM = "short_term"       # 短期记忆 (< 1小时)
    MID_TERM = "mid_term"           # 中期记忆 (1小时~30天)
    LONG_TERM = "long_term"         # 长期记忆 (> 30天)


class MemoryCell(Cell):
    """
    通用记忆细胞
    
    负责存储和检索信息，支持不同类型的记忆。
    """
    
    def __init__(self, specialization: str = "general"):
        super().__init__(specialization)
        self.memory_store: Dict[str, dict] = {}
        self.memory_type = MemoryType.MID_TERM
        self.max_items = 1000
        self.ttl_days = 30  # 默认TTL为30天
    
    @property
    def cell_type(self) -> CellType:
        return CellType.MEMORY
    
    async def _process_signal(self, message: dict) -> Any:
        """
        处理记忆操作请求
        
        支持的消息类型：
        - 'store': 存储记忆
        - 'retrieve': 检索记忆
        - 'delete': 删除记忆
        - 'query': 搜索记忆
        """
        message_type = message.get('type', '')
        
        if message_type == 'store':
            return await self._store(
                key=message.get('key', ''),
                value=message.get('value', ''),
                context=message.get('context', ''),
                memory_type=message.get('memory_type', 'mid_term')
            )
        
        elif message_type == 'retrieve':
            return await self._retrieve(
                key=message.get('key', '')
            )
        
        elif message_type == 'delete':
            return await self._delete(
                key=message.get('key', '')
            )
        
        elif message_type == 'query':
            return await self._query(
                query=message.get('query', ''),
                limit=message.get('limit', 5)
            )
        
        return {'error': f"Unknown message type: {message_type}"}
    
    async def _store(self, key: str, value: Any, context: str = "", 
                    memory_type: str = "mid_term") -> Dict[str, Any]:
        """
        存储记忆
        
        Args:
            key: 记忆键
            value: 记忆值
            context: 上下文信息
            memory_type: 记忆类型
        
        Returns:
            存储结果
        """
        if not key:
            return {'success': False, 'error': 'Key is required'}
        
        # 检查容量
        if len(self.memory_store) >= self.max_items:
            self._evict_oldest()
        
        self.memory_store[key] = {
            'value': value,
            'context': context,
            'memory_type': memory_type,
            'created_at': datetime.now().isoformat(),
            'access_count': 0,
            'last_accessed': datetime.now().isoformat()
        }
        
        self.record_success()
        return {'success': True, 'key': key, 'stored_items': len(self.memory_store)}
    
    async def _retrieve(self, key: str) -> Dict[str, Any]:
        """
        检索记忆
        
        Args:
            key: 记忆键
        
        Returns:
            检索结果
        """
        if key in self.memory_store:
            item = self.memory_store[key]
            item['access_count'] += 1
            item['last_accessed'] = datetime.now().isoformat()
            
            self.record_success()
            return {
                'success': True,
                'value': item['value'],
                'context': item['context'],
                'memory_type': item['memory_type'],
                'access_count': item['access_count']
            }
        
        return {'success': False, 'error': 'Key not found'}
    
    async def _delete(self, key: str) -> Dict[str, Any]:
        """
        删除记忆
        
        Args:
            key: 记忆键
        
        Returns:
            删除结果
        """
        if key in self.memory_store:
            del self.memory_store[key]
            return {'success': True, 'remaining_items': len(self.memory_store)}
        
        return {'success': False, 'error': 'Key not found'}
    
    async def _query(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """
        搜索记忆（基于关键词匹配）
        
        Args:
            query: 搜索查询
            limit: 返回结果数量限制
        
        Returns:
            搜索结果
        """
        results = []
        
        for key, item in self.memory_store.items():
            content = str(item['value']) + str(item['context'])
            if query.lower() in content.lower():
                results.append({
                    'key': key,
                    'value': item['value'],
                    'context': item['context'],
                    'score': self._calculate_relevance(query, content)
                })
        
        # 按相关性排序
        results.sort(key=lambda x: x['score'], reverse=True)
        
        self.record_success()
        return {
            'success': True,
            'results': results[:limit],
            'total_found': len(results)
        }
    
    def _calculate_relevance(self, query: str, content: str) -> float:
        """计算关键词相关性"""
        query_words = query.lower().split()
        content_lower = content.lower()
        
        matches = sum(1 for word in query_words if word in content_lower)
        return matches / len(query_words) if query_words else 0.0
    
    def _evict_oldest(self):
        """淘汰最老的记忆（LFU策略）"""
        if not self.memory_store:
            return
        
        # 找到访问次数最少的
        lfu_key = min(
            self.memory_store.keys(),
            key=lambda k: self.memory_store[k]['access_count']
        )
        del self.memory_store[lfu_key]


class HippocampusCell(MemoryCell):
    """
    海马体细胞
    
    负责短期记忆，快速编码和线索检索。
    特性：
    - 容量小（最多100条）
    - 快速读写
    - 自动遗忘（1小时后）
    """
    
    def __init__(self):
        super().__init__(specialization="hippocampus")
        self.memory_type = MemoryType.SHORT_TERM
        self.max_items = 100
        self.ttl_days = 0  # 短期记忆无需TTL天数限制
        self.forget_interval = 3600  # 1小时后遗忘
    
    async def _store(self, key: str, value: Any, context: str = "", 
                    memory_type: str = "short_term") -> Dict[str, Any]:
        """存储短期记忆（添加时间戳）"""
        result = await super()._store(key, value, context, memory_type)
        
        # 添加遗忘时间
        if result['success']:
            forget_at = datetime.now().timestamp() + self.forget_interval
            self.memory_store[key]['forget_at'] = forget_at
        
        return result
    
    def update_activity(self):
        """更新活动状态（检查并清理过期记忆）"""
        super().update_activity()
        self._clean_expired_memories()
    
    def _clean_expired_memories(self):
        """清理过期记忆"""
        now = datetime.now().timestamp()
        expired_keys = [
            key for key, item in self.memory_store.items()
            if item.get('forget_at', float('inf')) < now
        ]
        
        for key in expired_keys:
            del self.memory_store[key]


class NeocortexCell(MemoryCell):
    """
    新皮层细胞
    
    负责长期记忆和知识图谱存储。
    特性：
    - 大容量（最多10000条）
    - 支持知识图谱结构
    - 语义关联检索
    """
    
    def __init__(self):
        super().__init__(specialization="neocortex")
        self.memory_type = MemoryType.LONG_TERM
        self.max_items = 10000
        self.ttl_days = 365
        
        # 知识图谱结构
        self.graph_nodes: Dict[str, dict] = {}
        self.graph_edges: List[tuple] = []
    
    async def _process_signal(self, message: dict) -> Any:
        """处理知识图谱操作"""
        message_type = message.get('type', '')
        
        if message_type == 'add_node':
            return await self._add_graph_node(
                node_id=message.get('node_id', ''),
                properties=message.get('properties', {})
            )
        
        elif message_type == 'add_edge':
            return await self._add_graph_edge(
                source=message.get('source', ''),
                target=message.get('target', ''),
                relation=message.get('relation', '')
            )
        
        elif message_type == 'graph_query':
            return await self._graph_query(
                query=message.get('query', ''),
                node_type=message.get('node_type', '')
            )
        
        return await super()._process_signal(message)
    
    async def _add_graph_node(self, node_id: str, properties: dict) -> Dict[str, Any]:
        """添加知识图谱节点"""
        if not node_id:
            return {'success': False, 'error': 'node_id is required'}
        
        self.graph_nodes[node_id] = {
            'id': node_id,
            'properties': properties,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        return {'success': True, 'node_count': len(self.graph_nodes)}
    
    async def _add_graph_edge(self, source: str, target: str, 
                             relation: str = "related_to") -> Dict[str, Any]:
        """添加知识图谱边"""
        if source not in self.graph_nodes or target not in self.graph_nodes:
            return {'success': False, 'error': 'Source or target node not found'}
        
        edge = (source, relation, target)
        if edge not in self.graph_edges:
            self.graph_edges.append(edge)
        
        return {'success': True, 'edge_count': len(self.graph_edges)}
    
    async def _graph_query(self, query: str, node_type: str = "") -> Dict[str, Any]:
        """
        查询知识图谱
        
        Args:
            query: 查询关键词
            node_type: 节点类型过滤
        
        Returns:
            查询结果
        """
        results = []
        
        for node_id, node in self.graph_nodes.items():
            if node_type and node.get('properties', {}).get('type') != node_type:
                continue
            
            content = json.dumps(node['properties'])
            if query.lower() in content.lower() or query.lower() in node_id.lower():
                # 找到相关节点及其邻居
                neighbors = self._get_neighbors(node_id)
                results.append({
                    'node': node,
                    'neighbors': neighbors,
                    'score': self._calculate_relevance(query, content)
                })
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return {'success': True, 'results': results}
    
    def _get_neighbors(self, node_id: str) -> List[dict]:
        """获取节点的邻居"""
        neighbors = []
        
        for source, relation, target in self.graph_edges:
            if source == node_id and target in self.graph_nodes:
                neighbors.append({
                    'node': self.graph_nodes[target],
                    'relation': relation,
                    'direction': 'out'
                })
            elif target == node_id and source in self.graph_nodes:
                neighbors.append({
                    'node': self.graph_nodes[source],
                    'relation': relation,
                    'direction': 'in'
                })
        
        return neighbors