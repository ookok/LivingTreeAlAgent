"""
实名认证模块
Real Name Verification Module

设计理念：
实名认证是企业版安全的核心 - 确保只有授权人员才能使用

认证方式：
1. 手机号认证 - 通过短信验证码验证
2. 身份证认证 - 通过身份证信息和公安库验证（可选）
3. 人脸识别 - 通过人脸比对验证（可选）

实名信息加密存储：
- 使用AES-256-GCM加密
- 密钥从机器特征派生
- 只有授权用户才能解密查看

用户限制：
- 最多5个实名用户
- 每个用户有唯一的user_id
- 用户可以切换设备但不能同时在线
"""

import json
import secrets
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .crypto_utils import get_crypto_utils, EncryptedData


class VerificationType(Enum):
    """认证类型"""
    PHONE_SMS = ("PHONE_SMS", "手机号短信验证")
    ID_CARD = ("ID_CARD", "身份证认证")
    FACE_RECOGNITION = ("FACE_RECOGNITION", "人脸识别")
    ADMIN_APPROVE = ("ADMIN_APPROVE", "管理员审批")
    
    def __init__(self, code: str, name: str):
        self.code = code
        self.name = name


class VerificationStatus(Enum):
    """认证状态"""
    PENDING = ("PENDING", "待验证")
    VERIFIED = ("VERIFIED", "已验证")
    REJECTED = ("REJECTED", "已拒绝")
    EXPIRED = ("EXPIRED", "已过期")
    REVOKED = ("REVOKED", "已撤销")
    
    def __init__(self, code: str, name: str):
        self.code = code
        self.name = name


@dataclass
class RealNameUser:
    """实名用户"""
    user_id: str                      # 用户ID
    real_name: str                    # 真实姓名（加密）
    id_number_hash: str               # 身份证号哈希（用于验证，不存储原始值）
    phone_encrypted: str               # 手机号（加密）
    verification_type: VerificationType  # 认证方式
    verified_at: str                  # 认证时间
    expires_at: str                   # 认证过期时间
    status: VerificationStatus        # 认证状态
    max_devices: int = 2             # 最大设备数
    current_devices: List[str] = field(default_factory=list)  # 当前设备列表
    metadata: Dict[str, Any] = field(default_factory=dict)    # 附加信息
    
    def to_dict(self) -> dict:
        return {
            'user_id': self.user_id,
            'verification_type': self.verification_type.code,
            'verified_at': self.verified_at,
            'expires_at': self.expires_at,
            'status': self.status.code,
            'max_devices': self.max_devices,
            'current_devices': self.current_devices,
            'metadata': self.metadata,
        }


@dataclass
class VerificationRequest:
    """认证请求"""
    request_id: str                   # 请求ID
    user_id: str                     # 用户ID
    real_name: str                   # 真实姓名
    id_number: str                    # 身份证号
    phone: str                        # 手机号
    verification_type: VerificationType  # 认证方式
    request_data: Dict[str, Any] = field(default_factory=dict)  # 附加请求数据
    created_at: str                   # 创建时间
    expires_at: str                   # 过期时间
    status: VerificationStatus       # 状态


@dataclass
class VerificationCode:
    """验证码"""
    code: str                         # 验证码
    phone: str                        # 手机号
    purpose: str                      # 用途
    created_at: str                   # 创建时间
    expires_at: str                   # 过期时间
    used: bool = False               # 是否已使用
    
    @property
    def is_expired(self) -> bool:
        exp_time = datetime.strptime(self.expires_at, "%Y%m%d%H%M%S")
        return datetime.now() > exp_time
    
    @property
    def is_valid(self) -> bool:
        return not self.used and not self.is_expired


class RealNameVerifier:
    """
    实名认证器
    
    功能：
    1. 生成短信验证码
    2. 验证短信验证码
    3. 实名信息加密存储
    4. 用户数量限制（最多5人）
    5. 设备管理
    """
    
    # 验证码有效期（分钟）
    SMS_CODE_VALIDITY = 5
    
    # 最大实名用户数
    MAX_REAL_NAME_USERS = 5
    
    def __init__(self, db_path: str = None):
        """
        初始化实名认证器
        
        Args:
            db_path: 数据库路径
        """
        if db_path:
            self.db_path = db_path
        else:
            from pathlib import Path
            user_dir = Path.home() / ".hermes-desktop"
            user_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(user_dir / "real_name_db.sqlite")
        
        self.crypto = get_crypto_utils()
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            -- 实名用户表
            CREATE TABLE IF NOT EXISTS real_name_users (
                user_id TEXT PRIMARY KEY,
                real_name_encrypted TEXT NOT NULL,
                id_number_hash TEXT,
                phone_encrypted TEXT,
                verification_type TEXT NOT NULL,
                verified_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT DEFAULT 'VERIFIED',
                max_devices INTEGER DEFAULT 2,
                current_devices TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}'
            );
            
            -- 验证码表
            CREATE TABLE IF NOT EXISTS verification_codes (
                code TEXT NOT NULL,
                phone TEXT NOT NULL,
                purpose TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                used_at TEXT,
                request_id TEXT,
                PRIMARY KEY (code, phone, purpose)
            );
            
            -- 认证请求表
            CREATE TABLE IF NOT EXISTS verification_requests (
                request_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                real_name_encrypted TEXT NOT NULL,
                id_number_encrypted TEXT,
                phone_encrypted TEXT,
                verification_type TEXT NOT NULL,
                request_data TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                processed_at TEXT,
                processed_by TEXT,
                process_result TEXT
            );
            
            -- 操作日志
            CREATE TABLE IF NOT EXISTS verification_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                user_id TEXT,
                request_id TEXT,
                details TEXT,
                created_at TEXT NOT NULL
            );
            
            -- 索引
            CREATE INDEX IF NOT EXISTS idx_users_status ON real_name_users(status);
            CREATE INDEX IF NOT EXISTS idx_codes_phone ON verification_codes(phone);
            CREATE INDEX IF NOT EXISTS idx_requests_status ON verification_requests(status);
        """)
        conn.commit()
        conn.close()
    
    def _generate_sms_code(self, length: int = 6) -> str:
        """生成短信验证码"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(length)])
    
    def send_verification_code(self, phone: str, purpose: str = "REAL_NAME_VERIFY") -> Tuple[bool, str]:
        """
        发送验证码
        
        Args:
            phone: 手机号
            purpose: 用途
        
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        import sqlite3
        
        code = self._generate_sms_code()
        now = datetime.now()
        created_at = now.strftime("%Y%m%d%H%M%S")
        expires_at = (now + timedelta(minutes=self.SMS_CODE_VALIDITY)).strftime("%Y%m%d%H%M%S")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 标记旧验证码为已过期
            cursor.execute(
                """UPDATE verification_codes 
                   SET used = 1 
                   WHERE phone = ? AND purpose = ? AND used = 0""",
                (phone, purpose)
            )
            
            # 插入新验证码
            cursor.execute(
                """INSERT INTO verification_codes 
                   (code, phone, purpose, created_at, expires_at, used)
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (code, phone, purpose, created_at, expires_at)
            )
            
            conn.commit()
            conn.close()
            
            # TODO: 实际发送短信
            # 在生产环境中，这里应该调用短信网关API
            # 现在模拟发送成功
            return True, f"验证码已发送: {code}"  # 仅用于测试
            
        except Exception as e:
            return False, f"发送失败: {str(e)}"
    
    def verify_sms_code(self, phone: str, code: str, purpose: str = "REAL_NAME_VERIFY") -> Tuple[bool, str]:
        """
        验证短信验证码
        
        Args:
            phone: 手机号
            code: 验证码
            purpose: 用途
        
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        import sqlite3
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                """SELECT * FROM verification_codes 
                   WHERE phone = ? AND code = ? AND purpose = ? AND used = 0""",
                (phone, code, purpose)
            )
            row = cursor.fetchone()
            
            if not row:
                return False, "验证码错误"
            
            expires_at = row['expires_at']
            exp_time = datetime.strptime(expires_at, "%Y%m%d%H%M%S")
            
            if datetime.now() > exp_time:
                return False, "验证码已过期"
            
            # 标记验证码为已使用
            cursor.execute(
                """UPDATE verification_codes 
                   SET used = 1, used_at = ?
                   WHERE phone = ? AND code = ? AND purpose = ?""",
                (datetime.now().strftime("%Y%m%d%H%M%S"), phone, code, purpose)
            )
            
            conn.commit()
            conn.close()
            
            return True, "验证成功"
            
        except Exception as e:
            return False, f"验证失败: {str(e)}"
    
    def register_real_name_user(
        self,
        user_id: str,
        real_name: str,
        id_number: str = None,
        phone: str = None,
        verification_type: VerificationType = VerificationType.PHONE_SMS
    ) -> Tuple[bool, str, Optional[RealNameUser]]:
        """
        注册实名用户
        
        Args:
            user_id: 用户ID
            real_name: 真实姓名
            id_number: 身份证号
            phone: 手机号
            verification_type: 认证方式
        
        Returns:
            Tuple[bool, str, RealNameUser]: (是否成功, 消息, 用户对象)
        """
        import sqlite3
        
        # 检查用户数量
        if not self.can_add_more_users():
            return False, f"实名用户数已达上限（{self.MAX_REAL_NAME_USERS}人）", None
        
        # 检查用户是否已存在
        existing = self.get_real_name_user(user_id)
        if existing:
            return False, "该用户已存在实名认证", existing
        
        # 加密敏感信息
        real_name_enc = self.crypto.encrypt_real_name(real_name, id_number or "")
        id_number_hash = hashlib.sha256(id_number.encode()).hexdigest() if id_number else None
        phone_enc = ""
        if phone:
            phone_data = self.crypto.encrypt_real_name(phone, "")
            phone_enc = phone_data.to_json()
        
        now = datetime.now()
        verified_at = now.strftime("%Y%m%d%H%M%S")
        expires_at = (now + timedelta(days=365)).strftime("%Y%m%d")  # 一年有效期
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """INSERT INTO real_name_users 
                   (user_id, real_name_encrypted, id_number_hash, phone_encrypted,
                    verification_type, verified_at, expires_at, status, current_devices)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    real_name_enc.to_json(),
                    id_number_hash,
                    phone_enc,
                    verification_type.code,
                    verified_at,
                    expires_at,
                    VerificationStatus.VERIFIED.code,
                    '[]'
                )
            )
            
            conn.commit()
            conn.close()
            
            user = RealNameUser(
                user_id=user_id,
                real_name=real_name_enc.to_json(),  # 返回加密数据
                id_number_hash=id_number_hash or "",
                phone_encrypted=phone_enc,
                verification_type=verification_type,
                verified_at=verified_at,
                expires_at=expires_at,
                status=VerificationStatus.VERIFIED,
                current_devices=[]
            )
            
            return True, "实名认证成功", user
            
        except Exception as e:
            return False, f"注册失败: {str(e)}", None
    
    def get_real_name_user(self, user_id: str) -> Optional[RealNameUser]:
        """
        获取实名用户
        
        Args:
            user_id: 用户ID
        
        Returns:
            RealNameUser: 用户对象
        """
        import sqlite3
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM real_name_users WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return RealNameUser(
            user_id=row['user_id'],
            real_name=row['real_name_encrypted'],
            id_number_hash=row['id_number_hash'] or "",
            phone_encrypted=row['phone_encrypted'] or "",
            verification_type=VerificationType(row['verification_type']),
            verified_at=row['verified_at'],
            expires_at=row['expires_at'],
            status=VerificationStatus(row['status']),
            max_devices=row['max_devices'],
            current_devices=json.loads(row['current_devices'] or '[]'),
            metadata=json.loads(row['metadata'] or '{}')
        )
    
    def get_all_real_name_users(self) -> List[RealNameUser]:
        """获取所有实名用户"""
        import sqlite3
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM real_name_users WHERE status = ?", (VerificationStatus.VERIFIED.code,))
        rows = cursor.fetchall()
        conn.close()
        
        users = []
        for row in rows:
            users.append(RealNameUser(
                user_id=row['user_id'],
                real_name=row['real_name_encrypted'],
                id_number_hash=row['id_number_hash'] or "",
                phone_encrypted=row['phone_encrypted'] or "",
                verification_type=VerificationType(row['verification_type']),
                verified_at=row['verified_at'],
                expires_at=row['expires_at'],
                status=VerificationStatus(row['status']),
                max_devices=row['max_devices'],
                current_devices=json.loads(row['current_devices'] or '[]'),
                metadata=json.loads(row['metadata'] or '{}')
            ))
        
        return users
    
    def can_add_more_users(self) -> bool:
        """检查是否可以添加更多用户"""
        import sqlite3
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM real_name_users WHERE status = ?",
            (VerificationStatus.VERIFIED.code,)
        )
        row = cursor.fetchone()
        conn.close()
        
        count = row['cnt'] if row else 0
        return count < self.MAX_REAL_NAME_USERS
    
    def get_user_count(self) -> int:
        """获取当前实名用户数"""
        import sqlite3
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM real_name_users WHERE status = ?",
            (VerificationStatus.VERIFIED.code,)
        )
        row = cursor.fetchone()
        conn.close()
        
        return row['cnt'] if row else 0
    
    def verify_real_name_user(self, user_id: str, id_number: str = None, phone: str = None) -> Tuple[bool, str]:
        """
        验证实名用户身份
        
        Args:
            user_id: 用户ID
            id_number: 身份证号
            phone: 手机号
        
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        user = self.get_real_name_user(user_id)
        
        if not user:
            return False, "用户不存在"
        
        if user.status != VerificationStatus.VERIFIED:
            return False, f"用户状态异常: {user.status.name}"
        
        # 验证身份证号
        if id_number:
            expected_hash = hashlib.sha256(id_number.encode()).hexdigest()
            if user.id_number_hash != expected_hash:
                return False, "身份证号验证失败"
        
        # 验证手机号
        if phone:
            phone_data = self.crypto.encrypt_real_name(phone, "")
            if user.phone_encrypted != phone_data.to_json():
                return False, "手机号验证失败"
        
        return True, "验证成功"
    
    def revoke_user(self, user_id: str, reason: str = "管理员撤销") -> Tuple[bool, str]:
        """
        撤销实名用户
        
        Args:
            user_id: 用户ID
            reason: 撤销原因
        
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        import sqlite3
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """UPDATE real_name_users 
                   SET status = ?, metadata = json_set(metadata, 'revoke_reason', ?)
                   WHERE user_id = ?""",
                (VerificationStatus.REVOKED.code, reason, user_id)
            )
            
            conn.commit()
            conn.close()
            
            return True, "撤销成功"
            
        except Exception as e:
            return False, f"撤销失败: {str(e)}"
    
    def decrypt_real_name(self, encrypted_data: str) -> Tuple[str, str]:
        """
        解密实名信息
        
        Args:
            encrypted_data: 加密的数据
        
        Returns:
            Tuple[str, str]: (真实姓名, 身份证号)
        """
        try:
            enc_data = EncryptedData.from_json(encrypted_data)
            return self.crypto.decrypt_real_name(enc_data)
        except Exception:
            return "", ""


# 单例
_verifier: Optional[RealNameVerifier] = None


def get_real_name_verifier() -> RealNameVerifier:
    """获取实名认证器单例"""
    global _verifier
    if _verifier is None:
        _verifier = RealNameVerifier()
    return _verifier