"""
记忆巩固模块 - 模拟睡眠过程中的记忆巩固

功能：
1. 定期将海马体中的短期记忆转移到新皮层
2. Hebbian学习增强
3. 记忆重构
"""

import logging
import time
import threading
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ConsolidationStrategy(Enum):
    """记忆巩固策略"""
    HEBBIAN = "hebbian"           # Hebbian学习规则
    SPARSE_CODING = "sparse_coding"  # 稀疏编码
    REPLAY = "replay"             # 记忆重放
    DEEP_SLEEP = "deep_sleep"     # 深度睡眠模拟


class ConsolidationPhase(Enum):
    """巩固阶段"""
    ENCODING = "encoding"         # 编码阶段
    CONSOLIDATION = "consolidation"  # 巩固阶段
    INTEGRATION = "integration"   # 整合阶段
    REST = "rest"                 # 休息阶段


class MemoryConsolidator:
    """
    记忆巩固器 - 模拟大脑睡眠过程中的记忆巩固
    
    工作流程：
    1. 从海马体获取需要巩固的记忆
    2. 应用巩固策略增强记忆
    3. 将巩固后的记忆转移到新皮层
    4. 建立知识图谱连接
    """
    
    def __init__(
        self,
        hippocampus,
        neocortex,
        strategy: ConsolidationStrategy = ConsolidationStrategy.HEBBIAN,
        consolidation_interval: int = 3600  # 1小时
    ):
        self.hippocampus = hippocampus
        self.neocortex = neocortex
        self.strategy = strategy
        self.consolidation_interval = consolidation_interval
        
        self._phase = ConsolidationPhase.REST
        self._running = False
        self._thread = None
        self._last_consolidation = 0
        
        # 巩固统计
        self._stats = {
            'total_consolidated': 0,
            'total_transferred': 0,
            'failed_transfers': 0,
            'last_run': None
        }
    
    def start(self):
        """启动记忆巩固线程"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._consolidation_loop,
            daemon=True,
            name="MemoryConsolidator"
        )
        self._thread.start()
        logger.info("记忆巩固器已启动")
    
    def stop(self):
        """停止记忆巩固线程"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("记忆巩固器已停止")
    
    def _consolidation_loop(self):
        """巩固循环"""
        while self._running:
            current_time = time.time()
            
            # 检查是否需要进行巩固
            if current_time - self._last_consolidation >= self.consolidation_interval:
                self._perform_consolidation()
            
            time.sleep(60)  # 每分钟检查一次
    
    def _perform_consolidation(self):
        """执行记忆巩固"""
        logger.info("开始记忆巩固...")
        self._phase = ConsolidationPhase.CONSOLIDATION
        
        try:
            # 1. 获取需要巩固的记忆
            consolidated_ids = self.hippocampus.consolidate(target_level=0.8)
            logger.debug(f"发现 {len(consolidated_ids)} 个需要转移的记忆")
            
            # 2. 转移到新皮层
            transferred_count = 0
            for memory_id in consolidated_ids:
                if self._transfer_to_neocortex(memory_id):
                    transferred_count += 1
                else:
                    self._stats['failed_transfers'] += 1
            
            # 3. 整合知识图谱
            self._integrate_knowledge()
            
            # 更新统计
            self._stats['total_consolidated'] += len(consolidated_ids)
            self._stats['total_transferred'] += transferred_count
            self._stats['last_run'] = time.time()
            
            logger.info(f"记忆巩固完成：{transferred_count}/{len(consolidated_ids)} 成功转移")
            
        except Exception as e:
            logger.error(f"记忆巩固失败: {e}")
        
        self._phase = ConsolidationPhase.REST
        self._last_consolidation = time.time()
    
    def _transfer_to_neocortex(self, memory_id: str) -> bool:
        """将记忆从海马体转移到新皮层"""
        try:
            # 获取海马体中的记忆
            trace = self.hippocampus.get_memory(memory_id)
            if not trace:
                return False
            
            # 在新皮层创建语义节点
            node_id = self.neocortex.store_semantic(
                content=trace.content,
                node_type=trace.memory_type.value,
                metadata=trace.metadata
            )
            
            # 根据巩固策略增强相关连接
            self._apply_strategy(trace, node_id)
            
            # 从海马体删除已巩固的记忆（可选）
            # self.hippocampus.delete_memory(memory_id)
            
            logger.debug(f"转移记忆: {memory_id} -> {node_id}")
            return True
            
        except Exception as e:
            logger.error(f"转移记忆失败 {memory_id}: {e}")
            return False
    
    def _apply_strategy(self, trace, node_id: str):
        """应用巩固策略"""
        if self.strategy == ConsolidationStrategy.HEBBIAN:
            self._apply_hebbian(trace, node_id)
        elif self.strategy == ConsolidationStrategy.SPARSE_CODING:
            self._apply_sparse_coding(trace, node_id)
        elif self.strategy == ConsolidationStrategy.REPLAY:
            self._apply_replay(trace, node_id)
        elif self.strategy == ConsolidationStrategy.DEEP_SLEEP:
            self._apply_deep_sleep(trace, node_id)
    
    def _apply_hebbian(self, trace, node_id: str):
        """应用Hebbian学习规则"""
        # 找到相关节点并增强连接
        related_nodes = self.neocortex.retrieve_semantic(
            trace.content,
            limit=5,
            threshold=0.5
        )
        
        for related in related_nodes:
            if related['node_id'] != node_id:
                weight = related['similarity'] * trace.weight
                self.neocortex.connect_nodes(node_id, related['node_id'], weight)
    
    def _apply_sparse_coding(self, trace, node_id: str):
        """应用稀疏编码"""
        # 只保留最强的连接
        related_nodes = self.neocortex.retrieve_semantic(
            trace.content,
            limit=3,
            threshold=0.6
        )
        
        for related in related_nodes:
            if related['node_id'] != node_id:
                self.neocortex.connect_nodes(node_id, related['node_id'], 0.9)
    
    def _apply_replay(self, trace, node_id: str):
        """应用记忆重放"""
        # 模拟记忆重放增强
        trace.weight = min(2.0, trace.weight * 1.1)
        
        # 连接到时间相近的记忆
        recent_memories = self.hippocampus.get_all_memories()
        recent_memories.sort(key=lambda x: x['created_at'], reverse=True)
        
        for recent in recent_memories[:5]:
            recent_node = self.neocortex.get_node(recent['memory_id'])
            if recent_node and recent['memory_id'] != node_id:
                self.neocortex.connect_nodes(node_id, recent['memory_id'], 0.3)
    
    def _apply_deep_sleep(self, trace, node_id: str):
        """应用深度睡眠模拟"""
        # 深度睡眠期间的记忆重构
        related_nodes = self.neocortex.retrieve_semantic(
            trace.content,
            limit=10,
            threshold=0.3
        )
        
        # 建立更多弱连接（模拟记忆重构）
        for related in related_nodes:
            if related['node_id'] != node_id:
                weight = related['similarity'] * 0.5
                self.neocortex.connect_nodes(node_id, related['node_id'], weight)
    
    def _integrate_knowledge(self):
        """整合知识图谱"""
        # 找到相似节点并建立连接
        all_nodes = self.neocortex.get_all_nodes()
        
        for i, node1 in enumerate(all_nodes):
            for j, node2 in enumerate(all_nodes[i+1:], i+1):
                # 计算相似度
                similarity = self._calculate_content_similarity(
                    node1['content'],
                    node2['content']
                )
                
                if similarity > 0.4 and node2['node_id'] not in node1.get('connections', []):
                    self.neocortex.connect_nodes(
                        node1['node_id'],
                        node2['node_id'],
                        similarity
                    )
    
    def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """计算内容相似度"""
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def manual_consolidation(self, target_level: float = 0.8) -> Dict:
        """手动触发记忆巩固"""
        logger.info("手动触发记忆巩固")
        self._phase = ConsolidationPhase.CONSOLIDATION
        
        try:
            consolidated_ids = self.hippocampus.consolidate(target_level=target_level)
            transferred_count = 0
            
            for memory_id in consolidated_ids:
                if self._transfer_to_neocortex(memory_id):
                    transferred_count += 1
            
            self._integrate_knowledge()
            
            self._stats['total_consolidated'] += len(consolidated_ids)
            self._stats['total_transferred'] += transferred_count
            self._stats['last_run'] = time.time()
            
            return {
                'success': True,
                'consolidated': len(consolidated_ids),
                'transferred': transferred_count,
                'phase': self._phase.value
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'phase': self._phase.value
            }
    
    def get_stats(self) -> Dict:
        """获取巩固统计"""
        return {
            'strategy': self.strategy.value,
            'phase': self._phase.value,
            'running': self._running,
            'consolidation_interval': self.consolidation_interval,
            'stats': self._stats,
            'hippocampus': self.hippocampus.get_statistics(),
            'neocortex': self.neocortex.get_graph_summary()
        }
    
    def set_strategy(self, strategy: ConsolidationStrategy):
        """设置巩固策略"""
        self.strategy = strategy
        logger.info(f"切换巩固策略: {strategy.value}")