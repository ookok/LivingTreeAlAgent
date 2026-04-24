"""
数据库层 (Database Layer)
结构化数据查询与向量化

特性:
- 自然语言到 SQL 的转换
- 数据库内容向量化
- SQL 结果缓存
- 多表关联支持
"""

import time
import hashlib
import re
from typing import Optional, Dict, Any, List
from collections import defaultdict
import threading
from core.logger import get_logger
logger = get_logger('fusion_rag.database_layer')



class DatabaseLayer:
    """数据库查询层 - 结构化数据"""
    
    def __init__(self, cache_size: int = 1000):
        """
        初始化数据库层
        
        Args:
            cache_size: SQL 缓存大小
        """
        # 数据存储 (模拟数据库)
        self.tables: Dict[str, List[Dict]] = defaultdict(list)
        
        # SQL 缓存
        self.sql_cache: Dict[str, Any] = {}
        self.cache_size = cache_size
        
        # 向量化缓存
        self.vector_cache: Dict[str, List[float]] = {}
        
        # 统计
        self.query_count = 0
        self.cache_hit_count = 0
        self.lock = threading.Lock()
        
        logger.info(f"[DatabaseLayer] 初始化完成，缓存容量: {cache_size}")
    
    def _generate_sql_cache_key(self, sql_template: str, params: tuple) -> str:
        """生成 SQL 缓存键"""
        key_str = f"{sql_template}:{params}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _nl_to_keywords(self, query: str) -> List[str]:
        """自然语言转关键词"""
        # 移除停用词
        stopwords = {"的", "是", "在", "有", "和", "与", "或", "一个", "什么", "如何", "怎么", "多少"}
        
        words = re.findall(r'[\w]+', query.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 1]
        
        return keywords
    
    def _generate_record_embedding(self, record: Dict) -> List[float]:
        """生成记录嵌入"""
        # 将记录转换为自然语言描述
        parts = []
        for key, value in record.items():
            if key in ("id", "table"):
                continue
            parts.append(f"{key}是{value}")
        
        text = "，".join(parts)
        
        # 简单哈希嵌入
        vec = [0.0] * 64
        for i, char in enumerate(text):
            vec[ord(char) % 64] += 1.0
        
        # 归一化
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        
        return vec
    
    def add_record(self, record: Dict) -> None:
        """
        添加记录
        
        Args:
            record: {"table": "table_name", ...}
        """
        with self.lock:
            table_name = record.get("table", "default")
            
            # 生成嵌入
            embedding = self._generate_record_embedding(record)
            record["_embedding"] = embedding
            
            self.tables[table_name].append(record)
            
            # 清除相关缓存
            self.sql_cache.clear()
    
    def add_table_schema(self, table_name: str, schema: Dict) -> None:
        """
        添加表结构
        
        Args:
            table_name: 表名
            schema: {"columns": ["id", "name", ...], "types": {...}}
        """
        with self.lock:
            self.tables[f"_schema_{table_name}"] = [schema]
    
    def query(
        self,
        nl_query: str,
        table_hint: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        自然语言查询
        
        Args:
            nl_query: 自然语言查询
            table_hint: 表名提示
            
        Returns:
            查询结果列表
        """
        with self.lock:
            self.query_count += 1
            
            # 生成 SQL 缓存键
            keywords = self._nl_to_keywords(nl_query)
            cache_key = ":".join(keywords[:5])
            
            # 检查缓存
            if cache_key in self.sql_cache:
                self.cache_hit_count += 1
                return self.sql_cache[cache_key]
            
            # 分析查询意图
            results = []
            
            # 确定目标表
            target_tables = []
            if table_hint:
                target_tables = [table_hint]
            else:
                # 扫描所有表
                for table_name in self.tables:
                    if not table_name.startswith("_"):
                        target_tables.append(table_name)
            
            # 在各表中搜索
            for table_name in target_tables:
                records = self.tables.get(table_name, [])
                
                for record in records:
                    # 计算相关性
                    score = 0.0
                    
                    for keyword in keywords:
                        keyword_lower = keyword.lower()
                        
                        # 检查所有字段
                        for key, value in record.items():
                            if key.startswith("_"):
                                continue
                            
                            value_str = str(value).lower()
                            
                            if keyword_lower in value_str:
                                score += 1.0
                                break
                        
                        # 向量相似度
                        if "_embedding" in record:
                            # 简单关键词匹配作为近似
                            pass
                    
                    if score > 0:
                        results.append({
                            "record": {k: v for k, v in record.items() if not k.startswith("_")},
                            "table": table_name,
                            "score": score
                        })
            
            # 排序
            results.sort(key=lambda x: x["score"], reverse=True)
            
            # 缓存结果
            if len(self.sql_cache) >= self.cache_size:
                # LRU 淘汰
                first_key = next(iter(self.sql_cache))
                del self.sql_cache[first_key]
            
            self.sql_cache[cache_key] = results[:10]
            
            return results[:10]
    
    def execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        """
        执行 SQL (模拟)
        
        Args:
            sql: SQL 语句
            
        Returns:
            查询结果
        """
        with self.lock:
            self.query_count += 1
            
            # 缓存键
            cache_key = hashlib.md5(sql.encode()).hexdigest()
            
            if cache_key in self.sql_cache:
                self.cache_hit_count += 1
                return self.sql_cache[cache_key]
            
            # 简单 SQL 解析
            # SELECT * FROM table WHERE condition
            results = []
            
            # 解析表名
            match = re.search(r'FROM\s+(\w+)', sql, re.IGNORECASE)
            if match:
                table_name = match.group(1)
                records = self.tables.get(table_name, [])
                
                # 解析 WHERE
                where_match = re.search(r'WHERE\s+(\w+)\s*=\s*["\']?([^"\']+)["\']?', sql, re.IGNORECASE)
                if where_match:
                    field, value = where_match.groups()
                    for record in records:
                        if str(record.get(field, "")) == value:
                            results.append(record)
                else:
                    results = records[:10]
            
            # 缓存
            self.sql_cache[cache_key] = results
            
            return results
    
    def vectorize_content(self, content: str) -> List[float]:
        """
        将内容向量化
        
        Args:
            content: 文本内容
            
        Returns:
            向量
        """
        if content in self.vector_cache:
            return self.vector_cache[content]
        
        vec = [0.0] * 64
        for i, char in enumerate(content):
            vec[ord(char) % 64] += 1.0
        
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        
        self.vector_cache[content] = vec
        return vec
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_records = sum(len(records) for name, records in self.tables.items() if not name.startswith("_"))
        
        return {
            "table_count": len([n for n in self.tables if not n.startswith("_")]),
            "total_records": total_records,
            "query_count": self.query_count,
            "cache_hit_rate": self.cache_hit_count / max(self.query_count, 1),
            "cache_size": len(self.sql_cache),
            "vector_cache_size": len(self.vector_cache)
        }
