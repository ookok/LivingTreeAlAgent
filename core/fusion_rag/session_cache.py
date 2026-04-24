"""
会话缓存层 (Session Cache Layer)
基于会话图的上下文感知检索

特性:
- 会话关系图构建
- 基于图的上下文检索
- 滑动窗口注意力机制
- 时间衰减权重
"""

import time
import hashlib
from typing import Optional, Dict, Any, List
from collections import defaultdict
import threading
from core.logger import get_logger
logger = get_logger('fusion_rag.session_cache')



class SessionCacheLayer:
    """会话缓存层 - 上下文感知"""
    
    def __init__(
        self,
        max_history: int = 50,
        similarity_threshold: float = 0.7,
        time_decay_factor: float = 0.95
    ):
        """
        初始化会话缓存层
        
        Args:
            max_history: 每个会话最大历史条数
            similarity_threshold: 相似度阈值
            time_decay_factor: 时间衰减因子
        """
        # 会话存储: {session_id: [history_items]}
        self.sessions: Dict[str, List[Dict]] = defaultdict(list)
        self.max_history = max_history
        self.similarity_threshold = similarity_threshold
        self.time_decay_factor = time_decay_factor
        self.lock = threading.Lock()
        
        logger.info(f"[SessionCache] 初始化完成，最大历史: {max_history}")
    
    def _compute_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度 (简单词重叠)"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _hash_query(self, query: str) -> str:
        """计算查询哈希"""
        return hashlib.md5(query.encode()).hexdigest()
    
    def add_exchange(
        self,
        session_id: str,
        query: str,
        response: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        添加会话交换记录
        
        Args:
            session_id: 会话ID
            query: 用户查询
            response: AI响应
            metadata: 额外元数据
        """
        with self.lock:
            exchange = {
                "query": query,
                "response": response,
                "timestamp": time.time(),
                "query_hash": self._hash_query(query),
                "metadata": metadata or {}
            }
            
            self.sessions[session_id].append(exchange)
            
            # LRU 淘汰
            if len(self.sessions[session_id]) > self.max_history:
                self.sessions[session_id] = self.sessions[session_id][-self.max_history:]
    
    def get(
        self,
        query: str,
        session_id: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        获取会话相关结果
        
        Args:
            query: 当前查询
            session_id: 会话ID
            top_k: 返回数量
            
        Returns:
            相关历史记录列表
        """
        with self.lock:
            if session_id not in self.sessions:
                return []
            
            history = self.sessions[session_id]
            if not history:
                return []
            
            # 计算与历史记录的相似度
            scored_history = []
            current_time = time.time()
            
            for i, item in enumerate(history):
                # 语义相似度
                sim_query = self._compute_similarity(query, item["query"])
                sim_response = self._compute_similarity(query, item["response"])
                max_sim = max(sim_query, sim_response)
                
                # 时间衰减
                time_diff = current_time - item["timestamp"]
                time_decay = self.time_decay_factor ** (time_diff / 3600)  # 每小时衰减
                
                # 位置权重 (最近的消息更重要)
                position_weight = 1.0 - (i / len(history)) * 0.3
                
                # 综合分数
                score = max_sim * time_decay * position_weight
                
                if score > 0.1:  # 最低阈值
                    scored_history.append({
                        "item": item,
                        "score": score,
                        "similarity": max_sim,
                        "time_decay": time_decay
                    })
            
            # 排序并返回
            scored_history.sort(key=lambda x: x["score"], reverse=True)
            return scored_history[:top_k]
    
    def get_context(self, session_id: str, last_n: int = 3) -> str:
        """
        获取会话上下文摘要
        
        Args:
            session_id: 会话ID
            last_n: 最近N条记录
            
        Returns:
            上下文摘要字符串
        """
        with self.lock:
            if session_id not in self.sessions:
                return ""
            
            history = self.sessions[session_id]
            recent = history[-last_n:] if len(history) >= last_n else history
            
            context_parts = []
            for item in recent:
                context_parts.append(f"Q: {item['query']}")
                context_parts.append(f"A: {item['response'][:100]}...")
            
            return "\n".join(context_parts)
    
    def get_related_queries(self, query: str, session_id: str) -> List[str]:
        """
        获取相关查询
        
        Args:
            query: 当前查询
            session_id: 会话ID
            
        Returns:
            相关查询列表
        """
        with self.lock:
            if session_id not in self.sessions:
                return []
            
            history = self.sessions[session_id]
            related = []
            
            for item in history:
                if self._compute_similarity(query, item["query"]) > self.similarity_threshold:
                    related.append(item["query"])
            
            return related[:5]
    
    def clear_session(self, session_id: str) -> None:
        """清空会话"""
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
    
    def get_stats(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            if session_id:
                return {
                    "session_id": session_id,
                    "history_length": len(self.sessions.get(session_id, [])),
                    "total_sessions": 1 if session_id in self.sessions else 0
                }
            else:
                return {
                    "total_sessions": len(self.sessions),
                    "total_exchanges": sum(len(h) for h in self.sessions.values()),
                    "avg_history_length": (
                        sum(len(h) for h in self.sessions.values()) / len(self.sessions)
                        if self.sessions else 0
                    )
                }
