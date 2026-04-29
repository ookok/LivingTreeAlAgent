"""
邮箱地址与身份管理

管理去中心化邮箱地址 (user@nodeid.p2p)、身份密钥、地址簿
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Optional

from .models import MailboxAddress, Contact, TrustLevel

logger = logging.getLogger(__name__)


class AddressManager:
    """
    地址管理器
    
    负责:
    - 生成节点ID
    - 管理邮箱地址
    - 存储联系人地址簿
    - 信任级别管理
    """
    
    def __init__(self, data_dir: str = "~/.hermes-desktop/mailbox"):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 节点身份
        self.node_id: Optional[str] = None
        self.private_key: Optional[bytes] = None
        self.public_key: Optional[bytes] = None
        
        # 当前用户
        self.current_user: Optional[str] = None
        self.current_address: Optional[MailboxAddress] = None
        
        # 数据库
        self.db_path = self.data_dir / "addresses.db"
        self._init_db()
        
        # 联系人缓存
        self._contacts_cache: dict[str, Contact] = {}
        self._address_cache: dict[str, MailboxAddress] = {}
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 节点身份表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                public_key TEXT,
                private_key_encrypted TEXT,
                created_at REAL,
                last_seen REAL
            )
        """)
        
        # 联系人表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                address TEXT PRIMARY KEY,
                username TEXT,
                node_id TEXT,
                display_name TEXT,
                public_key TEXT,
                trust_level INTEGER,
                total_sent INTEGER DEFAULT 0,
                total_received INTEGER DEFAULT 0,
                last_contact_at REAL,
                tags TEXT,
                is_blocked INTEGER DEFAULT 0,
                notes TEXT,
                created_at REAL
            )
        """)
        
        # 地址解析缓存表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS address_resolve_cache (
                address TEXT PRIMARY KEY,
                node_id TEXT,
                public_key TEXT,
                resolved_at REAL,
                expires_at REAL
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Address database initialized: {self.db_path}")
    
    # ========== 节点身份管理 ==========
    
    def generate_node_identity(self, username: str) -> MailboxAddress:
        """
        生成新的节点身份
        
        Args:
            username: 用户名
            
        Returns:
            MailboxAddress: 新的邮箱地址
        """
        # 生成安全的节点ID
        random_bytes = secrets.token_bytes(32)
        self.node_id = hashlib.sha256(random_bytes).hexdigest()[:16]
        
        # 生成密钥对 (简化版, 实际应用应使用更安全的方案)
        self.private_key = secrets.token_bytes(32)
        self.public_key = hashlib.sha256(self.private_key).digest()
        
        self.current_user = username
        self.current_address = MailboxAddress(
            username=username,
            node_id=self.node_id,
            public_key=self.public_key.hex()
        )
        
        # 存储到数据库
        self._save_node_identity()
        
        logger.info(f"Generated new node identity: {self.current_address}")
        return self.current_address
    
    def load_node_identity(self) -> Optional[MailboxAddress]:
        """
        加载已存在的节点身份
        
        Returns:
            MailboxAddress or None
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT node_id, username, public_key FROM nodes ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            self.node_id = row[0]
            self.current_user = row[1]
            self.public_key = bytes.fromhex(row[2])
            self.current_address = MailboxAddress(
                username=self.current_user,
                node_id=self.node_id,
                public_key=row[2]
            )
            logger.info(f"Loaded node identity: {self.current_address}")
            return self.current_address
        
        return None
    
    def _save_node_identity(self):
        """保存节点身份到数据库"""
        if not self.current_address:
            return
            
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO nodes (node_id, username, public_key, created_at, last_seen)
            VALUES (?, ?, ?, ?, ?)
        """, (
            self.node_id,
            self.current_user,
            self.public_key.hex() if self.public_key else None,
            time.time(),
            time.time()
        ))
        
        conn.commit()
        conn.close()
    
    # ========== 地址解析 ==========
    
    def parse_address(self, address_str: str) -> Optional[MailboxAddress]:
        """
        解析邮箱地址字符串
        
        Args:
            address_str: 地址字符串 (如 user@nodeid.p2p)
            
        Returns:
            MailboxAddress or None
        """
        # 检查缓存
        if address_str in self._address_cache:
            return self._address_cache[address_str]
        
        try:
            if address_str.endswith(".p2p"):
                username, rest = address_str.rsplit("@", 1)
                node_id = rest[:-4]  # 去掉 .p2p
                
                addr = MailboxAddress(
                    username=username,
                    node_id=node_id
                )
                self._address_cache[address_str] = addr
                return addr
        except Exception as e:
            logger.error(f"Failed to parse address: {address_str}, {e}")
        
        return None
    
    def resolve_address(self, address_str: str, public_key: Optional[str] = None) -> Optional[MailboxAddress]:
        """
        解析并验证地址 (可含公钥)
        
        Args:
            address_str: 地址字符串
            public_key: 公钥 (可选)
            
        Returns:
            MailboxAddress or None
        """
        addr = self.parse_address(address_str)
        if addr and public_key:
            addr.public_key = public_key
        return addr
    
    def register_public_key(self, address: MailboxAddress, public_key: str):
        """
        注册联系人的公钥
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO address_resolve_cache (address, node_id, public_key, resolved_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(address),
            address.node_id,
            public_key,
            time.time(),
            time.time() + 86400 * 7  # 7天过期
        ))
        
        conn.commit()
        conn.close()
        
        address.public_key = public_key
        self._address_cache[str(address)] = address
        logger.debug(f"Registered public key for {address}")
    
    # ========== 联系人管理 ==========
    
    def add_contact(self, contact: Contact) -> bool:
        """
        添加联系人
        
        Args:
            contact: 联系人对象
            
        Returns:
            bool: 是否成功
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO contacts (
                    address, username, node_id, display_name, public_key,
                    trust_level, total_sent, total_received, last_contact_at,
                    tags, is_blocked, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(contact.address),
                contact.address.username,
                contact.address.node_id,
                contact.display_name,
                contact.address.public_key,
                contact.trust_level.value,
                contact.total_sent,
                contact.total_received,
                contact.last_contact_at,
                ",".join(contact.tags),
                int(contact.is_blocked),
                contact.notes,
                time.time()
            ))
            
            conn.commit()
            conn.close()
            
            self._contacts_cache[str(contact.address)] = contact
            logger.info(f"Added contact: {contact.address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add contact: {e}")
            return False
    
    def get_contact(self, address: MailboxAddress) -> Optional[Contact]:
        """获取联系人"""
        addr_str = str(address)
        
        if addr_str in self._contacts_cache:
            return self._contacts_cache[addr_str]
        
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM contacts WHERE address = ?", (addr_str,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            contact = Contact(
                address=MailboxAddress(
                    username=row["username"],
                    node_id=row["node_id"],
                    public_key=row["public_key"]
                ),
                display_name=row["display_name"] or "",
                trust_level=TrustLevel(row["trust_level"]),
                total_sent=row["total_sent"],
                total_received=row["total_received"],
                last_contact_at=row["last_contact_at"],
                tags=row["tags"].split(",") if row["tags"] else [],
                is_blocked=bool(row["is_blocked"]),
                notes=row["notes"] or ""
            )
            self._contacts_cache[addr_str] = contact
            return contact
        
        return None
    
    def get_all_contacts(self) -> list[Contact]:
        """获取所有联系人"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM contacts ORDER BY last_contact_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        contacts = []
        for row in rows:
            contact = Contact(
                address=MailboxAddress(
                    username=row["username"],
                    node_id=row["node_id"],
                    public_key=row["public_key"]
                ),
                display_name=row["display_name"] or "",
                trust_level=TrustLevel(row["trust_level"]),
                total_sent=row["total_sent"],
                total_received=row["total_received"],
                last_contact_at=row["last_contact_at"],
                tags=row["tags"].split(",") if row["tags"] else [],
                is_blocked=bool(row["is_blocked"]),
                notes=row["notes"] or ""
            )
            contacts.append(contact)
        
        return contacts
    
    def update_contact_stats(self, address: MailboxAddress, sent: bool = False, received: bool = False):
        """更新联系人统计"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        if sent:
            cursor.execute("UPDATE contacts SET total_sent = total_sent + 1 WHERE address = ?", (str(address),))
        if received:
            cursor.execute("UPDATE contacts SET total_received = total_received + 1 WHERE address = ?", (str(address),))
        
        cursor.execute("UPDATE contacts SET last_contact_at = ? WHERE address = ?", (time.time(), str(address)))
        
        conn.commit()
        conn.close()
        
        # 清除缓存
        self._contacts_cache.pop(str(address), None)
    
    def set_trust_level(self, address: MailboxAddress, level: TrustLevel):
        """设置信任级别"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("UPDATE contacts SET trust_level = ? WHERE address = ?", (level.value, str(address)))
        
        conn.commit()
        conn.close()
        
        # 清除缓存
        self._contacts_cache.pop(str(address), None)
        
        logger.info(f"Set trust level for {address}: {level}")
    
    def block_address(self, address: MailboxAddress):
        """拉黑地址"""
        self.set_trust_level(address, TrustLevel.BLOCKED)
    
    def is_blocked(self, address: MailboxAddress) -> bool:
        """检查是否被拉黑"""
        contact = self.get_contact(address)
        return contact is not None and contact.trust_level == TrustLevel.BLOCKED
    
    # ========== 地址簿导入导出 ==========
    
    def export_address_book(self) -> list[dict]:
        """导出地址簿"""
        contacts = self.get_all_contacts()
        return [
            {
                "address": str(c.address),
                "display_name": c.display_name,
                "public_key": c.address.public_key,
                "trust_level": c.trust_level.name,
                "tags": c.tags
            }
            for c in contacts
        ]
    
    def import_address_book(self, data: list[dict]) -> int:
        """导入地址簿"""
        count = 0
        for item in data:
            try:
                addr = self.parse_address(item["address"])
                if addr:
                    contact = Contact(
                        address=addr,
                        display_name=item.get("display_name", ""),
                        trust_level=TrustLevel[item.get("trust_level", "UNKNOWN")],
                        tags=item.get("tags", [])
                    )
                    if item.get("public_key"):
                        addr.public_key = item["public_key"]
                    self.add_contact(contact)
                    count += 1
            except Exception as e:
                logger.error(f"Failed to import contact: {e}")
        
        return count
    
    # ========== 工具方法 ==========
    
    @property
    def my_address(self) -> Optional[MailboxAddress]:
        """获取当前用户地址"""
        return self.current_address
    
    def get_my_full_address(self) -> str:
        """获取当前用户完整地址字符串"""
        if self.current_address:
            return self.current_address.full_address
        return ""
    
    def verify_address_format(self, address_str: str) -> bool:
        """验证地址格式"""
        return self.parse_address(address_str) is not None
