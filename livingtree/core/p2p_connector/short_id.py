"""
短ID生成器

生成8-12位纯数字短码，映射到完整节点ID
支持: 雪花算法、随机数、自定义前缀
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ShortIDGenerator:
    """
    短ID生成器
    
    多种生成策略:
    1. 雪花算法 (Snowflake) - 时间+机器+序列
    2. 随机数 + 校验位
    3. 哈希 + 进制转换
    """
    
    # ID长度选项
    LENGTH_8 = 8
    LENGTH_10 = 10
    LENGTH_12 = 12
    
    def __init__(self, data_dir: str = "~/.hermes-desktop/connector"):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 数据库 - 短ID -> 节点ID 映射
        self.db_path = self.data_dir / "short_ids.db"
        self._init_db()
        
        # 雪花算法状态
        self._snowflake_epoch = 1700000000000  # 2023-11-15
        self._snowflake_machine_id = secrets.token_bytes(2)[0] % 1024
        self._snowflake_sequence = 0
        self._snowflake_last_time = 0
        self._snowflake_lock = 0
        
        # 我的短ID
        self._my_short_id: Optional[str] = None
        self._my_node_id: Optional[str] = None
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS short_id_mapping (
                short_id TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                created_at REAL,
                last_used REAL,
                use_count INTEGER DEFAULT 0,
                is_mine INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS id_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_id TEXT,
                node_id TEXT,
                action TEXT,
                timestamp REAL
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_node_id ON short_id_mapping(node_id)")
        
        conn.commit()
        conn.close()
        logger.info(f"Short ID database initialized: {self.db_path}")
    
    # ========== 生成策略 ==========
    
    def generate_snowflake(self, length: int = LENGTH_10) -> str:
        """
        雪花算法生成短ID
        
        结构: 时间戳(41位) + 机器ID(10位) + 序列号(12位)
        实际使用时会压缩到指定位数
        
        Args:
            length: ID长度 (8/10/12)
            
        Returns:
            str: 纯数字短ID
        """
        import threading
        
        with threading.Lock():
            now = int(time.time() * 1000) - self._snowflake_epoch
            
            if now == self._snowflake_last_time:
                self._snowflake_sequence = (self._snowflake_sequence + 1) & 4095
            else:
                self._snowflake_sequence = 0
            
            self._snowflake_last_time = now
            
            # 组合ID
            snowflake_id = (
                (now << 22) |
                (self._snowflake_machine_id << 12) |
                self._snowflake_sequence
            )
        
        # 转换为纯数字并截取指定长度
        id_str = str(snowflake_id)
        
        if length == self.LENGTH_8:
            # 取后8位 + 校验位
            base = id_str[-8:]
            return self._add_check_digit(base[:7])
        elif length == self.LENGTH_12:
            return id_str[:12]
        else:  # 10
            return id_str[:10]
    
    def generate_random(self, length: int = LENGTH_10) -> str:
        """
        随机数生成短ID
        
        Args:
            length: ID长度
            
        Returns:
            str: 纯数字短ID
        """
        if length == self.LENGTH_8:
            max_val = 10_000_000  # 7位 + 1位校验
            base = secrets.randbelow(max_val)
            return self._add_check_digit(base)
        elif length == self.LENGTH_12:
            max_val = 10_000_000_000  # 11位 + 1位校验
            base = secrets.randbelow(max_val)
            return self._add_check_digit_12(str(base).zfill(11))
        else:  # 10
            max_val = 100_000_000  # 9位 + 1位校验
            base = secrets.randbelow(max_val)
            return self._add_check_digit(str(base).zfill(9))
    
    def generate_from_node_id(self, node_id: str, length: int = LENGTH_10) -> str:
        """
        从节点ID哈希生成短ID
        
        同一节点ID总是生成相同的短ID
        
        Args:
            node_id: 节点ID
            length: ID长度
            
        Returns:
            str: 纯数字短ID
        """
        # SHA256哈希
        hash_bytes = hashlib.sha256(node_id.encode()).digest()
        hash_int = int.from_bytes(hash_bytes[:8], 'big')
        
        # 取指定位数
        if length == self.LENGTH_8:
            short = str(hash_int % 10_000_000).zfill(7)
            return self._add_check_digit(short)
        elif length == self.LENGTH_12:
            short = str(hash_int % 100_000_000_000).zfill(11)
            return self._add_check_digit_12(short)
        else:  # 10
            short = str(hash_int % 100_000_000).zfill(9)
            return self._add_check_digit(str(short))
    
    def _add_check_digit(self, base: str) -> str:
        """
        添加校验位 (Luhn算法)
        
        Args:
            base: 7或9位数字
            
        Returns:
            str: 8或10位数字
        """
        digits = [int(c) for c in base]
        
        # Luhn算法
        checksum = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 0:
                d *= 2
                if d > 9:
                    d -= 9
            checksum += d
        
        check_digit = (10 - (checksum % 10)) % 10
        return base + str(check_digit)
    
    def _add_check_digit_12(self, base: str) -> str:
        """12位ID的校验位"""
        digits = [int(c) for c in base]
        
        checksum = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 0:
                d *= 2
                if d > 9:
                    d -= 9
            checksum += d
        
        check_digit = (10 - (checksum % 10)) % 10
        return base + str(check_digit)
    
    def verify_check_digit(self, short_id: str) -> bool:
        """
        验证校验位
        
        Args:
            short_id: 短ID
            
        Returns:
            bool: 是否有效
        """
        if len(short_id) < 2:
            return False
        
        base = short_id[:-1]
        expected = self._add_check_digit(base) if len(base) in (7, 9) else self._add_check_digit_12(base)
        
        return short_id == expected
    
    # ========== 短ID管理 ==========
    
    def register_short_id(self, short_id: str, node_id: str, is_mine: bool = False) -> bool:
        """
        注册短ID映射
        
        Args:
            short_id: 短ID
            node_id: 完整节点ID
            is_mine: 是否是我的ID
            
        Returns:
            bool: 是否成功
        """
        try:
            # 验证格式
            if not short_id.isdigit():
                logger.error(f"Invalid short ID: {short_id}")
                return False
            
            if not self.verify_check_digit(short_id):
                logger.warning(f"Short ID check digit invalid: {short_id}")
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO short_id_mapping 
                (short_id, node_id, created_at, last_used, use_count, is_mine)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (short_id, node_id, time.time(), time.time(), 0, int(is_mine)))
            
            # 记录历史
            cursor.execute("""
                INSERT INTO id_history (short_id, node_id, action, timestamp)
                VALUES (?, ?, ?, ?)
            """, (short_id, node_id, "register" if not is_mine else "mine", time.time()))
            
            conn.commit()
            conn.close()
            
            if is_mine:
                self._my_short_id = short_id
                self._my_node_id = node_id
            
            logger.info(f"Registered short ID: {short_id} -> {node_id[:16]}...")
            return True
            
        except Exception as e:
            logger.error(f"Register short ID failed: {e}")
            return False
    
    def resolve_short_id(self, short_id: str) -> Optional[str]:
        """
        解析短ID获取节点ID
        
        Args:
            short_id: 短ID
            
        Returns:
            str: 节点ID 或 None
        """
        # 检查校验位
        if not self.verify_check_digit(short_id):
            logger.warning(f"Invalid short ID check digit: {short_id}")
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT node_id FROM short_id_mapping 
            WHERE short_id = ?
        """, (short_id,))
        
        row = cursor.fetchone()
        
        if row:
            # 更新使用时间
            cursor.execute("""
                UPDATE short_id_mapping 
                SET last_used = ?, use_count = use_count + 1
                WHERE short_id = ?
            """, (time.time(), short_id))
            conn.commit()
        
        conn.close()
        
        return row[0] if row else None
    
    def resolve_node_id(self, node_id: str) -> Optional[str]:
        """
        反向查询 - 通过节点ID获取短ID
        
        Args:
            node_id: 节点ID
            
        Returns:
            str: 短ID 或 None
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT short_id FROM short_id_mapping 
            WHERE node_id = ?
        """, (node_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else None
    
    def get_my_short_id(self) -> Optional[str]:
        """获取我的短ID"""
        if self._my_short_id:
            return self._my_short_id
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT short_id, node_id FROM short_id_mapping 
            WHERE is_mine = 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            self._my_short_id = row[0]
            self._my_node_id = row[1]
        
        return self._my_short_id
    
    def get_all_mappings(self) -> list:
        """获取所有映射"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT short_id, node_id, created_at, last_used, use_count 
            FROM short_id_mapping
            ORDER BY last_used DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "short_id": r[0],
                "node_id": r[1],
                "created_at": r[2],
                "last_used": r[3],
                "use_count": r[4]
            }
            for r in rows
        ]
    
    # ========== 便捷方法 ==========
    
    def generate_and_register(self, node_id: str, length: int = LENGTH_10) -> str:
        """
        生成并注册短ID
        
        Args:
            node_id: 节点ID
            length: ID长度
            
        Returns:
            str: 生成的短ID
        """
        # 优先从节点ID哈希生成 (保证一致性)
        short_id = self.generate_from_node_id(node_id, length)
        
        # 检查是否已存在
        existing = self.resolve_node_id(node_id)
        if existing:
            return existing
        
        # 检查冲突
        while self.resolve_short_id(short_id):
            # 冲突, 换一个随机生成
            short_id = self.generate_random(length)
        
        # 注册
        self.register_short_id(short_id, node_id, is_mine=True)
        
        return short_id
    
    def delete_short_id(self, short_id: str) -> bool:
        """删除短ID映射"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM short_id_mapping WHERE short_id = ?", (short_id,))
            
            cursor.execute("""
                INSERT INTO id_history (short_id, node_id, action, timestamp)
                VALUES (?, ?, ?, ?)
            """, (short_id, "", "delete", time.time()))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Delete short ID failed: {e}")
            return False
