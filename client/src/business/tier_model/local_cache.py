"""
L2 本地缓存模块
基于 SQLite + 哈希索引 + 语义索引的本地缓存实现
"""

import sqlite3
import json
import os
import hashlib
import time
from typing import Optional, Any, Dict, List, Tuple
from threading import RLock
from dataclasses import dataclass


@dataclass
class LocalCacheEntry:
    """本地缓存条目"""
    id: int
    query_hash: str
    query: str
    context_hash: str
    response: str
    model_id: str
    created_at: float
    last_accessed: float
    access_count: int
    heat_weight: float


class LocalCache:
    """
    L2 本地缓存
    - 存储：SQLite + 序列化文件
    - 容量：10,000条
    - 索引：哈希索引 + 语义索引
    - 过期：24小时TTL + 访问频率更新
    """
    
    def __init__(self, db_path: str = "~/.hermes-desktop/cache/conversation.db",
                 max_items: int = 10000, ttl_seconds: int = 86400,
                 index_type: str = "hybrid"):
        self.db_path = os.path.expanduser(db_path)
        self.max_items = max_items
        self.ttl_seconds = ttl_seconds
        self.index_type = index_type
        self._lock = RLock()
        self._hits = 0
        self._misses = 0
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_hash TEXT NOT NULL UNIQUE,
                query TEXT NOT NULL,
                context_hash TEXT,
                response TEXT NOT NULL,
                model_id TEXT,
                created_at REAL NOT NULL,
                last_accessed REAL NOT NULL,
                access_count INTEGER DEFAULT 1,
                heat_weight REAL DEFAULT 1.0
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_hash ON conversation_cache(query_hash)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at ON conversation_cache(created_at)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_access_count ON conversation_cache(access_count)
        """)
        
        if self.index_type in ("semantic", "hybrid"):
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_tokens (
                    cache_id INTEGER PRIMARY KEY,
                    tokens TEXT NOT NULL,
                    FOREIGN KEY (cache_id) REFERENCES conversation_cache(id)
                )
            """)
        
        conn.commit()
        conn.close()
    
    def _generate_hash(self, query: str, context: str = None) -> str:
        """生成查询哈希"""
        content = f"{query}|{context or ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        import re
        tokens = re.findall(r'\w+', text.lower())
        return list(set(tokens))[:50]
    
    def get(self, query: str, context: str = None) -> Optional[Dict[str, Any]]:
        """获取缓存"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            
            query_hash = self._generate_hash(query, context)
            current_time = time.time()
            
            cursor.execute("""
                SELECT id, query_hash, query, context_hash, response, model_id,
                       created_at, last_accessed, access_count, heat_weight
                FROM conversation_cache
                WHERE query_hash = ?
            """, (query_hash,))
            
            row = cursor.fetchone()
            
            if row is None:
                self._misses += 1
                conn.close()
                return None
            
            entry = LocalCacheEntry(*row)
            
            effective_ttl = self.ttl_seconds * entry.heat_weight
            if (current_time - entry.created_at) > effective_ttl:
                cursor.execute("DELETE FROM conversation_cache WHERE id = ?", (entry.id,))
                conn.commit()
                self._misses += 1
                conn.close()
                return None
            
            cursor.execute("""
                UPDATE conversation_cache
                SET last_accessed = ?, access_count = access_count + 1
                WHERE id = ?
            """, (current_time, entry.id))
            conn.commit()
            
            if entry.access_count > 5:
                new_heat = min(2.0, 1.0 + (entry.access_count - 5) * 0.05)
                cursor.execute("""
                    UPDATE conversation_cache SET heat_weight = ? WHERE id = ?
                """, (new_heat, entry.id))
                conn.commit()
            
            self._hits += 1
            conn.close()
            
            return {
                "response": entry.response,
                "model_id": entry.model_id,
                "created_at": entry.created_at
            }
    
    def set(self, query: str, response: Any, context: str = None, model_id: str = None):
        """设置缓存"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            
            query_hash = self._generate_hash(query, context)
            context_hash = hashlib.sha256((context or '').encode()).hexdigest()[:16]
            current_time = time.time()
            
            if isinstance(response, (dict, list)):
                response_str = json.dumps(response, ensure_ascii=False)
            else:
                response_str = str(response)
            
            try:
                cursor.execute("""
                    INSERT INTO conversation_cache 
                    (query_hash, query, context_hash, response, model_id, created_at, last_accessed, access_count, heat_weight)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1.0)
                """, (query_hash, query, context_hash, response_str, model_id, current_time, current_time))
            except sqlite3.IntegrityError:
                cursor.execute("""
                    UPDATE conversation_cache
                    SET response = ?, model_id = ?, created_at = ?
                    WHERE query_hash = ?
                """, (response_str, model_id, current_time, query_hash))
            
            if self.index_type in ("semantic", "hybrid"):
                tokens = self._tokenize(query)
                cursor.execute("""
                    INSERT OR REPLACE INTO cache_tokens (cache_id, tokens)
                    VALUES (
                        (SELECT id FROM conversation_cache WHERE query_hash = ?),
                        ?
                    )
                """, (query_hash, json.dumps(tokens)))
            
            cursor.execute("SELECT COUNT(*) FROM conversation_cache")
            count = cursor.fetchone()[0]
            
            if count > self.max_items:
                cursor.execute("""
                    DELETE FROM conversation_cache
                    WHERE id IN (
                        SELECT id FROM conversation_cache
                        ORDER BY heat_weight * access_count ASC, last_accessed ASC
                        LIMIT ?
                    )
                """, (count - self.max_items,))
            
            if count % 100 == 0:
                self._cleanup_expired(cursor)
            
            conn.commit()
            conn.close()
    
    def _cleanup_expired(self, cursor):
        """清理过期条目"""
        current_time = time.time()
        cursor.execute("""
            DELETE FROM conversation_cache
            WHERE (created_at + (86400 * heat_weight)) < ?
        """, (current_time,))
    
    def search_by_tokens(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """基于tokens的模糊搜索"""
        if self.index_type not in ("semantic", "hybrid"):
            return []
        
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            
            query_tokens = set(self._tokenize(query))
            
            cursor.execute("""
                SELECT c.id, c.query, c.response, c.access_count, ct.tokens
                FROM conversation_cache c
                JOIN cache_tokens ct ON c.id = ct.cache_id
                ORDER BY c.access_count DESC
                LIMIT 100
            """)
            
            results = []
            for row in cursor.fetchall():
                cache_tokens = set(json.loads(row[4]))
                intersection = len(query_tokens & cache_tokens)
                union = len(query_tokens | cache_tokens)
                similarity = intersection / union if union > 0 else 0
                
                if similarity > 0.3:
                    results.append({
                        "id": row[0],
                        "query": row[1],
                        "response": row[2],
                        "access_count": row[3],
                        "similarity": similarity
                    })
            
            results.sort(key=lambda x: x["similarity"], reverse=True)
            conn.close()
            
            return results[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM conversation_cache")
            count = cursor.fetchone()[0]
            
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            
            conn.close()
            
            return {
                "size": count,
                "max_size": self.max_items,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "ttl_seconds": self.ttl_seconds,
                "index_type": self.index_type
            }
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversation_cache")
            cursor.execute("DELETE FROM cache_tokens")
            conn.commit()
            conn.close()
            self._hits = 0
            self._misses = 0
