"""
SQLite FTS5 全文搜索模块
用于高速文件搜索
"""

import sqlite3
import threading
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class SearchHit:
    """搜索命中"""
    rowid: int
    filename: str
    path: str
    rank: float


class SQLiteFTSSearch:
    """
    SQLite FTS5 全文搜索引擎
    
    支持:
    - 前缀搜索 (query*)
    - 布尔搜索 (word1 AND word2)
    - 短语搜索 ("exact phrase")
    - 模糊搜索 (fuzzy matching)
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
    
    def connect(self):
        """连接数据库"""
        with self._lock:
            if self._conn is None:
                self._conn = sqlite3.connect(
                    self.db_path,
                    check_same_thread=False
                )
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA synchronous=NORMAL")
                self._conn.execute("PRAGMA cache_size=-64000")  # 64MB
    
    def close(self):
        """关闭连接"""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
    
    def ensure_fts_table(self):
        """确保 FTS 表存在"""
        self.connect()
        cursor = self._conn.cursor()
        
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                filename,
                path,
                content='files',
                content_rowid='id',
                tokenize='unicode61 remove_diacritics 2'
            )
        ''')
        
        self._conn.commit()
    
    def rebuild_fts(self):
        """重建 FTS 索引"""
        self.connect()
        cursor = self._conn.cursor()
        
        # 删除旧 FTS 表
        cursor.execute("DROP TABLE IF EXISTS files_fts")
        
        # 重建
        cursor.execute('''
            CREATE VIRTUAL TABLE files_fts USING fts5(
                filename,
                path,
                content='files',
                content_rowid='id',
                tokenize='unicode61 remove_diacritics 2'
            )
        ''')
        
        # 填充数据
        cursor.execute('''
            INSERT INTO files_fts(rowid, filename, path)
            SELECT id, filename, path FROM files
        ''')
        
        self._conn.commit()
    
    def search(
        self,
        query: str,
        limit: int = 50,
        include_path: bool = True
    ) -> List[SearchHit]:
        """
        搜索
        
        Args:
            query: 搜索查询（支持 FTS5 语法）
            limit: 返回数量
            include_path: 是否搜索路径
            
        Returns:
            搜索命中列表
        """
        self.connect()
        cursor = self._conn.cursor()
        
        results = []
        
        try:
            if include_path:
                sql = '''
                    SELECT files_fts.rowid, files_fts.filename, files_fts.path, files_fts.rank
                    FROM files_fts
                    WHERE files_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                '''
                cursor.execute(sql, (query, limit))
            else:
                sql = '''
                    SELECT files_fts.rowid, files_fts.filename, files_fts.path, files_fts.rank
                    FROM files_fts
                    WHERE filename MATCH ?
                    ORDER BY rank
                    LIMIT ?
                '''
                cursor.execute(sql, (query, limit))
            
            for row in cursor.fetchall():
                results.append(SearchHit(
                    rowid=row[0],
                    filename=row[1],
                    path=row[2],
                    rank=row[3] or 0
                ))
                
        except sqlite3.Error as e:
            print(f"FTS 搜索失败: {e}")
        
        return results
    
    def search_prefix(self, prefix: str, limit: int = 50) -> List[SearchHit]:
        """前缀搜索"""
        return self.search(f"{prefix}*", limit)
    
    def search_phrase(self, phrase: str, limit: int = 50) -> List[SearchHit]:
        """短语搜索"""
        return self.search(f'"{phrase}"', limit)
    
    def search_boolean(self, terms: List[str], operator: str = "AND", limit: int = 50) -> List[SearchHit]:
        """布尔搜索"""
        query = f" {operator} ".join(terms)
        return self.search(query, limit)
    
    def search_fuzzy(
        self,
        term: str,
        limit: int = 50,
        max_edits: int = 2
    ) -> List[SearchHit]:
        """
        模糊搜索（基于编辑距离）
        
        注意: SQLite FTS5 不原生支持模糊搜索，这里模拟实现
        """
        self.connect()
        cursor = self._conn.cursor()
        
        # 使用 LIKE 进行近似匹配
        pattern = f"%{term}%"
        sql = '''
            SELECT id, filename, path, 0 as rank
            FROM files
            WHERE filename LIKE ?
            ORDER BY filename
            LIMIT ?
        '''
        
        results = []
        cursor.execute(sql, (pattern, limit))
        
        for row in cursor.fetchall():
            results.append(SearchHit(
                rowid=row[0],
                filename=row[1],
                path=row[2],
                rank=row[3]
            ))
        
        return results
    
    def autocomplete(self, prefix: str, limit: int = 10) -> List[str]:
        """
        自动补全
        
        返回以 prefix 开头的唯一文件名
        """
        self.connect()
        cursor = self._conn.cursor()
        
        sql = '''
            SELECT DISTINCT filename
            FROM files
            WHERE filename LIKE ?
            ORDER BY filename
            LIMIT ?
        '''
        
        results = []
        cursor.execute(sql, (f"{prefix}%", limit))
        
        for row in cursor.fetchall():
            results.append(row[0])
        
        return results
    
    def get_stats(self) -> Dict:
        """获取统计"""
        self.connect()
        cursor = self._conn.cursor()
        
        stats = {}
        
        try:
            cursor.execute("SELECT COUNT(*) FROM files_fts")
            stats["fts_count"] = cursor.fetchone()[0]
            
            cursor.execute("PRAGMA index_list(files_fts)")
            stats["indices"] = cursor.fetchall()
        except:
            pass
        
        return stats
    
    def optimize(self):
        """优化 FTS 索引"""
        self.connect()
        self._conn.execute("INSERT INTO files_fts(files_fts) VALUES('optimize')")
        self._conn.commit()
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # 测试
    import os
    import tempfile
    
    db_path = os.path.join(tempfile.gettempdir(), "test_fts.db")
    
    # 创建测试数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            path TEXT
        )
    ''')
    
    # 插入测试数据
    test_files = [
        ("python.py", "/path/to/python.py"),
        ("python_script.py", "/path/to/python_script.py"),
        ("main.py", "/path/to/main.py"),
        ("README.md", "/path/to/README.md"),
        ("document.txt", "/path/to/document.txt"),
        ("data.csv", "/path/to/data.csv"),
        ("image.png", "/path/to/image.png"),
    ]
    
    cursor.executemany("INSERT INTO files (filename, path) VALUES (?, ?)", test_files)
    conn.commit()
    conn.close()
    
    # 测试 FTS
    fts = SQLiteFTSSearch(db_path)
    
    print("FTS5 测试")
    print("-" * 50)
    
    print("\n1. 前缀搜索 'python':")
    results = fts.search_prefix("python")
    for r in results:
        print(f"  {r.filename}")
    
    print("\n2. 短语搜索 'python script':")
    results = fts.search_phrase("python script")
    for r in results:
        print(f"  {r.filename}")
    
    print("\n3. 自动补全 'py':")
    results = fts.autocomplete("py")
    for r in results:
        print(f"  {r}")
    
    print("\n4. 模糊搜索 'pyhon':")
    results = fts.search_fuzzy("pyhon")
    for r in results:
        print(f"  {r.filename}")
    
    fts.close()
    
    # 清理
    os.remove(db_path)
