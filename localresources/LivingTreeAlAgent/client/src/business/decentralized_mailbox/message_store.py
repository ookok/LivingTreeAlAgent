"""
消息存储引擎

管理邮件消息的本地存储、索引、检索
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional, List

from .models import (MailMessage, MailboxAddress, Attachment, MessageStatus,
                    InboxFolder, DEFAULT_FOLDERS, DeliveryReceipt)

logger = logging.getLogger(__name__)


class MessageStore:
    """
    消息存储引擎
    
    功能:
    - SQLite本地存储
    - 邮件索引与检索
    - 文件夹管理
    - 附件存储
    """
    
    # 附件大小阈值 (1MB, 小于此存数据库, 以上存文件系统)
    ATTACHMENT_DB_THRESHOLD = 1024 * 1024
    
    def __init__(self, data_dir: str = "~/.hermes-desktop/mailbox"):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 附件存储目录
        self.attachment_dir = self.data_dir / "attachments"
        self.attachment_dir.mkdir(exist_ok=True)
        
        # 数据库
        self.db_path = self.data_dir / "messages.db"
        self._init_db()
        
        # 缓存
        self._message_cache: dict[str, MailMessage] = {}
        self._cache_enabled = True
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 消息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                subject TEXT,
                body TEXT,
                body_plain TEXT,
                from_addr TEXT,
                to_addrs TEXT,
                cc_addrs TEXT,
                bcc_addrs TEXT,
                created_at REAL,
                sent_at REAL,
                delivered_at REAL,
                read_at REAL,
                status TEXT,
                is_encrypted INTEGER,
                is_signed INTEGER,
                has_large_attachment INTEGER,
                thread_id TEXT,
                reply_to_id TEXT,
                priority INTEGER,
                labels TEXT,
                is_starred INTEGER,
                is_deleted INTEGER
            )
        """)
        
        # 附件表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                chunk_id TEXT PRIMARY KEY,
                message_id TEXT,
                filename TEXT,
                file_size INTEGER,
                content_type TEXT,
                checksum TEXT,
                total_chunks INTEGER,
                chunk_index INTEGER,
                storage_path TEXT,
                status TEXT,
                created_at REAL,
                FOREIGN KEY (message_id) REFERENCES messages(message_id)
            )
        """)
        
        # 投递回执表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS delivery_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                recipient TEXT,
                status TEXT,
                delivered_at REAL,
                read_at REAL,
                error_message TEXT
            )
        """)
        
        # 文件夹表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                folder_id TEXT PRIMARY KEY,
                name TEXT,
                icon TEXT,
                parent_id TEXT
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_from ON messages(from_addr)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_addrs)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id)")
        
        conn.commit()
        conn.close()
        
        # 初始化默认文件夹
        self._init_default_folders()
        logger.info(f"Message database initialized: {self.db_path}")
    
    def _init_default_folders(self):
        """初始化默认文件夹"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        for folder in DEFAULT_FOLDERS:
            cursor.execute("""
                INSERT OR IGNORE INTO folders (folder_id, name, icon, parent_id)
                VALUES (?, ?, ?, ?)
            """, (folder.folder_id, folder.name, folder.icon, folder.parent_id))
        
        conn.commit()
        conn.close()
    
    # ========== 消息CRUD ==========
    
    def save_message(self, message: MailMessage) -> bool:
        """
        保存消息
        
        Args:
            message: 邮件消息
            
        Returns:
            bool: 是否成功
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO messages (
                    message_id, subject, body, body_plain,
                    from_addr, to_addrs, cc_addrs, bcc_addrs,
                    created_at, sent_at, delivered_at, read_at,
                    status, is_encrypted, is_signed, has_large_attachment,
                    thread_id, reply_to_id, priority, labels,
                    is_starred, is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.message_id,
                message.subject,
                message.body,
                message.body_plain,
                str(message.from_addr) if message.from_addr else None,
                json.dumps([str(a) for a in message.to_addrs]),
                json.dumps([str(a) for a in message.cc_addrs]),
                json.dumps([str(a) for a in message.bcc_addrs]),
                message.created_at,
                message.sent_at,
                message.delivered_at,
                message.read_at,
                message.status.value,
                int(message.is_encrypted),
                int(message.is_signed),
                int(message.has_large_attachment),
                message.thread_id,
                message.reply_to_id,
                message.priority,
                ",".join(message.labels),
                int(message.is_starred),
                int(message.is_deleted)
            ))
            
            # 保存附件
            for attachment in message.attachments:
                self._save_attachment(cursor, attachment)
            
            conn.commit()
            conn.close()
            
            # 更新缓存
            if self._cache_enabled:
                self._message_cache[message.message_id] = message
            
            logger.debug(f"Saved message: {message.message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Save message failed: {e}")
            return False
    
    def _save_attachment(self, cursor, attachment: Attachment):
        """保存附件到数据库"""
        cursor.execute("""
            INSERT OR REPLACE INTO attachments (
                chunk_id, message_id, filename, file_size, content_type,
                checksum, total_chunks, chunk_index, storage_path, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            attachment.chunk_id,
            None,  # message_id later
            attachment.filename,
            attachment.file_size,
            attachment.content_type,
            attachment.checksum,
            attachment.total_chunks,
            attachment.chunk_index,
            attachment.storage_path,
            attachment.status.value,
            time.time()
        ))
    
    def get_message(self, message_id: str) -> Optional[MailMessage]:
        """获取消息"""
        # 检查缓存
        if self._cache_enabled and message_id in self._message_cache:
            return self._message_cache[message_id]
        
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            message = self._row_to_message(row)
            if self._cache_enabled:
                self._message_cache[message_id] = message
            return message
        
        return None
    
    def _row_to_message(self, row: sqlite3.Row) -> MailMessage:
        """将数据库行转换为消息对象"""
        return MailMessage(
            message_id=row["message_id"],
            subject=row["subject"],
            body=row["body"],
            body_plain=row["body_plain"] or "",
            from_addr=MailboxAddress.parse(row["from_addr"]) if row["from_addr"] else None,
            to_addrs=[MailboxAddress.parse(a) for a in json.loads(row["to_addrs"])] if row["to_addrs"] else [],
            cc_addrs=[MailboxAddress.parse(a) for a in json.loads(row["cc_addrs"])] if row["cc_addrs"] else [],
            bcc_addrs=[MailboxAddress.parse(a) for a in json.loads(row["bcc_addrs"])] if row["bcc_addrs"] else [],
            created_at=row["created_at"],
            sent_at=row["sent_at"],
            delivered_at=row["delivered_at"],
            read_at=row["read_at"],
            status=MessageStatus(row["status"]),
            is_encrypted=bool(row["is_encrypted"]),
            is_signed=bool(row["is_signed"]),
            has_large_attachment=bool(row["has_large_attachment"]),
            thread_id=row["thread_id"],
            reply_to_id=row["reply_to_id"],
            priority=row["priority"],
            labels=row["labels"].split(",") if row["labels"] else [],
            is_starred=bool(row["is_starred"]),
            is_deleted=bool(row["is_deleted"])
        )
    
    def delete_message(self, message_id: str, hard: bool = False) -> bool:
        """
        删除消息
        
        Args:
            message_id: 消息ID
            hard: 是否永久删除
        """
        try:
            if hard:
                # 永久删除
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                # 删除附件
                cursor.execute("DELETE FROM attachments WHERE message_id = ?", (message_id,))
                cursor.execute("DELETE FROM messages WHERE message_id = ?", (message_id,))
                
                conn.commit()
                conn.close()
                
                # 删除本地文件
                self._delete_attachment_files(message_id)
            else:
                # 软删除
                self.get_message(message_id)
                if message_id in self._message_cache:
                    self._message_cache[message_id].is_deleted = True
                
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("UPDATE messages SET is_deleted = 1 WHERE message_id = ?", (message_id,))
                conn.commit()
                conn.close()
            
            # 清除缓存
            self._message_cache.pop(message_id, None)
            
            logger.debug(f"Deleted message: {message_id}, hard={hard}")
            return True
            
        except Exception as e:
            logger.error(f"Delete message failed: {e}")
            return False
    
    def _delete_attachment_files(self, message_id: str):
        """删除附件文件"""
        import shutil
        msg_attach_dir = self.attachment_dir / message_id
        if msg_attach_dir.exists():
            shutil.rmtree(str(msg_attach_dir))
    
    # ========== 检索 ==========
    
    def get_inbox(self, limit: int = 50, offset: int = 0) -> List[MailMessage]:
        """获取收件箱"""
        return self._get_messages_by_folder("inbox", limit, offset)
    
    def get_sent(self, limit: int = 50, offset: int = 0) -> List[MailMessage]:
        """获取已发送"""
        return self._get_messages_by_folder("sent", limit, offset)
    
    def get_drafts(self, limit: int = 50, offset: int = 0) -> List[MailMessage]:
        """获取草稿箱"""
        return self._get_messages_by_folder("drafts", limit, offset)
    
    def get_trash(self, limit: int = 50, offset: int = 0) -> List[MailMessage]:
        """获取垃圾箱"""
        return self._get_messages_by_folder("trash", limit, offset)
    
    def get_outbox(self, limit: int = 50, offset: int = 0) -> List[MailMessage]:
        """获取发件箱"""
        return self._get_messages_by_folder("outbox", limit, offset)
    
    def _get_messages_by_folder(self, folder: str, limit: int, offset: int) -> List[MailMessage]:
        """根据文件夹获取消息"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 收件箱: to_addrs包含我
        # 已发送: from_addr是我
        # 草稿箱: status=DRAFT
        # 垃圾箱: is_deleted=1
        # 发件箱: status=SENDING or status=FAILED
        
        if folder == "inbox":
            my_addr = ""  # 需要外部传入
            cursor.execute("""
                SELECT * FROM messages 
                WHERE to_addrs LIKE ? AND is_deleted = 0
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (f"%{my_addr}%", limit, offset))
        elif folder == "sent":
            cursor.execute("""
                SELECT * FROM messages 
                WHERE status = 'sent' AND is_deleted = 0
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
        elif folder == "drafts":
            cursor.execute("""
                SELECT * FROM messages 
                WHERE status = 'draft' AND is_deleted = 0
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
        elif folder == "trash":
            cursor.execute("""
                SELECT * FROM messages 
                WHERE is_deleted = 1
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
        elif folder == "outbox":
            cursor.execute("""
                SELECT * FROM messages 
                WHERE status IN ('sending', 'failed') AND is_deleted = 0
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
        else:
            cursor.execute("SELECT * FROM messages ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_message(row) for row in rows]
    
    def search_messages(self, query: str, my_address: str = "", limit: int = 50) -> List[MailMessage]:
        """
        搜索消息
        
        Args:
            query: 搜索关键词
            my_address: 我的地址 (用于过滤)
            limit: 返回数量
            
        Returns:
            List[MailMessage]
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        search_term = f"%{query}%"
        
        cursor.execute("""
            SELECT * FROM messages 
            WHERE is_deleted = 0 AND (
                subject LIKE ? OR 
                body_plain LIKE ? OR
                from_addr LIKE ? OR
                to_addrs LIKE ?
            )
            ORDER BY created_at DESC
            LIMIT ?
        """, (search_term, search_term, search_term, search_term, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_message(row) for row in rows]
    
    def get_unread_count(self, folder: str = "inbox") -> int:
        """获取未读数"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        if folder == "inbox":
            cursor.execute("""
                SELECT COUNT(*) FROM messages 
                WHERE status != 'read' AND is_deleted = 0
            """)
        else:
            cursor.execute("SELECT COUNT(*) FROM messages WHERE is_deleted = 0")
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    # ========== 消息状态更新 ==========
    
    def mark_as_read(self, message_id: str) -> bool:
        """标记为已读"""
        return self._update_status(message_id, read_at=time.time())
    
    def mark_as_sent(self, message_id: str) -> bool:
        """标记为已发送"""
        return self._update_status(message_id, sent_at=time.time(), 
                                  status=MessageStatus.SENT)
    
    def mark_as_delivered(self, message_id: str) -> bool:
        """标记为已送达"""
        return self._update_status(message_id, delivered_at=time.time(),
                                  status=MessageStatus.DELIVERED)
    
    def _update_status(self, message_id: str, status: MessageStatus = None, 
                       read_at: float = None, sent_at: float = None,
                       delivered_at: float = None) -> bool:
        """更新消息状态"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            updates = []
            params = []
            
            if status:
                updates.append("status = ?")
                params.append(status.value)
            if read_at:
                updates.append("read_at = ?")
                params.append(read_at)
            if sent_at:
                updates.append("sent_at = ?")
                params.append(sent_at)
            if delivered_at:
                updates.append("delivered_at = ?")
                params.append(delivered_at)
            
            if updates:
                params.append(message_id)
                cursor.execute(f"UPDATE messages SET {', '.join(updates)} WHERE message_id = ?", params)
                conn.commit()
            
            conn.close()
            
            # 更新缓存
            if message_id in self._message_cache:
                msg = self._message_cache[message_id]
                if status:
                    msg.status = status
                if read_at:
                    msg.read_at = read_at
            
            return True
            
        except Exception as e:
            logger.error(f"Update status failed: {e}")
            return False
    
    # ========== 附件存储 ==========
    
    def save_attachment_file(self, chunk_id: str, data: bytes) -> Optional[str]:
        """
        保存附件到文件系统
        
        Args:
            chunk_id: 分片ID
            data: 文件数据
            
        Returns:
            str: 存储路径
        """
        try:
            # 使用chunk_id作为文件名
            file_path = self.attachment_dir / f"{chunk_id}.bin"
            file_path.write_bytes(data)
            
            logger.debug(f"Saved attachment: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Save attachment failed: {e}")
            return None
    
    def load_attachment_file(self, chunk_id: str) -> Optional[bytes]:
        """加载附件文件"""
        try:
            file_path = self.attachment_dir / f"{chunk_id}.bin"
            if file_path.exists():
                return file_path.read_bytes()
            return None
        except Exception as e:
            logger.error(f"Load attachment failed: {e}")
            return None
    
    # ========== 文件夹管理 ==========
    
    def get_folders(self) -> List[InboxFolder]:
        """获取所有文件夹"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM folders")
        rows = cursor.fetchall()
        conn.close()
        
        folders = []
        for row in rows:
            folder = InboxFolder(
                folder_id=row["folder_id"],
                name=row["name"],
                icon=row["icon"],
                parent_id=row["parent_id"],
                unread_count=self.get_unread_count(row["folder_id"]),
                total_count=self._get_folder_count(row["folder_id"])
            )
            folders.append(folder)
        
        return folders
    
    def _get_folder_count(self, folder_id: str) -> int:
        """获取文件夹消息数"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        counts = {
            "inbox": "SELECT COUNT(*) FROM messages WHERE is_deleted = 0",
            "sent": "SELECT COUNT(*) FROM messages WHERE status = 'sent' AND is_deleted = 0",
            "drafts": "SELECT COUNT(*) FROM messages WHERE status = 'draft' AND is_deleted = 0",
            "trash": "SELECT COUNT(*) FROM messages WHERE is_deleted = 1",
            "outbox": "SELECT COUNT(*) FROM messages WHERE status IN ('sending', 'failed')"
        }
        
        query = counts.get(folder_id, "SELECT COUNT(*) FROM messages WHERE is_deleted = 0")
        cursor.execute(query)
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    # ========== 投递回执 ==========
    
    def add_delivery_receipt(self, receipt: DeliveryReceipt) -> bool:
        """添加投递回执"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO delivery_receipts (
                    message_id, recipient, status, delivered_at, read_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                receipt.message_id,
                receipt.recipient,
                receipt.status.value,
                receipt.delivered_at,
                receipt.read_at,
                receipt.error_message
            ))
            
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            logger.error(f"Add delivery receipt failed: {e}")
            return False


# 为MailboxAddress添加parse方法
class MailboxAddress:
    @staticmethod
    def parse(address_str: str) -> Optional[MailboxAddress]:
        """解析地址字符串"""
        if not address_str or "@" not in address_str:
            return None
        
        try:
            if address_str.endswith(".p2p"):
                username, rest = address_str.rsplit("@", 1)
                node_id = rest[:-4]
            else:
                username, node_id = address_str.rsplit("@", 1)
            
            return MailboxAddress(username=username, node_id=node_id)
        except:
            return None
