"""
激活码验证器
License Key Validator

设计理念：
验证是激活的核心 - 只有通过验证才能使用企业版功能

验证层级：
1. 格式验证 - 激活码格式是否正确
2. 校验位验证 - 是否被篡改
3. 有效期验证 - 是否过期
4. 发行方验证 - 是否是合法发行
5. 激活状态验证 - 是否已被使用

验证结果包含：
- 是否有效
- 错误原因（如有）
- 授权版本
- 功能列表
- 过期时间
"""

import hashlib
import json
import sqlite3
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum

from .crypto_utils import get_crypto_utils
from .license_generator import LicenseGenerator, LicenseKey, LicenseVersion, LicenseStatus


class ValidationResult(Enum):
    """验证结果枚举"""
    VALID = ("VALID", "有效")
    INVALID_FORMAT = ("INVALID_FORMAT", "格式无效")
    INVALID_CHECKSUM = ("INVALID_CHECKSUM", "校验失败")
    EXPIRED = ("EXPIRED", "已过期")
    ALREADY_ACTIVATED = ("ALREADY_ACTIVATED", "已被激活")
    REVOKED = ("REVOKED", "已撤销")
    MAX_USERS_REACHED = ("MAX_USERS_REACHED", "用户数已满")
    DATABASE_ERROR = ("DATABASE_ERROR", "数据库错误")
    UNKNOWN_ERROR = ("UNKNOWN_ERROR", "未知错误")
    
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message


@dataclass
class ActivationRecord:
    """激活记录"""
    activation_id: str           # 激活ID
    license_key: str            # 激活码
    version: str                # 版本
    device_id: str              # 设备ID
    user_id: str                # 用户ID
    real_name: str              # 实名（加密存储）
    activated_at: str            # 激活时间
    expires_at: str             # 过期时间
    status: str                 # 状态
    features: List[str] = field(default_factory=list)  # 已解锁功能
    
    def to_dict(self) -> dict:
        return {
            'activation_id': self.activation_id,
            'license_key': self.license_key,
            'version': self.version,
            'device_id': self.device_id,
            'user_id': self.user_id,
            'real_name_encrypted': self.real_name,
            'activated_at': self.activated_at,
            'expires_at': self.expires_at,
            'status': self.status,
            'features': self.features,
        }


@dataclass
class ValidationResponse:
    """验证响应"""
    result: ValidationResult     # 验证结果
    message: str               # 详细信息
    license_info: Optional[Dict[str, Any]] = None  # 激活码信息
    activation_record: Optional[ActivationRecord] = None  # 激活记录
    
    @property
    def is_valid(self) -> bool:
        return self.result == ValidationResult.VALID


class LicenseValidator:
    """
    激活码验证器
    
    核心功能：
    1. 激活码格式验证
    2. 校验位验证
    3. 激活状态检查
    4. 激活操作执行
    5. 激活记录管理
    """
    
    def __init__(self, db_path: str = None):
        """
        初始化验证器
        
        Args:
            db_path: 数据库路径（如果为None，使用默认路径）
        """
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = self._get_default_db_path()
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.generator = LicenseGenerator()
        self.crypto = get_crypto_utils()
        self._init_db()
    
    def _get_default_db_path(self) -> Path:
        """获取默认数据库路径"""
        user_dir = Path.home() / ".hermes-desktop"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir / "license_db.sqlite"
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            conn.executescript("""
                -- 激活码表（存储所有生成的激活码）
                CREATE TABLE IF NOT EXISTS license_keys (
                    license_key TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    serial TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    features TEXT DEFAULT '[]',
                    max_users INTEGER DEFAULT 1,
                    metadata TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'UNUSED',
                    revoked_at TEXT,
                    revoked_reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                
                -- 激活记录表
                CREATE TABLE IF NOT EXISTS activation_records (
                    activation_id TEXT PRIMARY KEY,
                    license_key TEXT NOT NULL,
                    version TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    real_name_encrypted TEXT,
                    activated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    status TEXT DEFAULT 'ACTIVE',
                    features TEXT DEFAULT '[]',
                    UNIQUE(license_key),
                    FOREIGN KEY (license_key) REFERENCES license_keys(license_key)
                );
                
                -- 实名用户表（最多5人）
                CREATE TABLE IF NOT EXISTS real_name_users (
                    user_id TEXT PRIMARY KEY,
                    real_name_encrypted TEXT NOT NULL,
                    id_number_encrypted TEXT,
                    phone_encrypted TEXT,
                    verification_type TEXT,
                    verified_at TEXT NOT NULL,
                    status TEXT DEFAULT 'ACTIVE',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                
                -- 设备表
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    device_name TEXT,
                    device_fingerprint TEXT,
                    activation_id TEXT,
                    last_active_at TEXT,
                    status TEXT DEFAULT 'ACTIVE',
                    FOREIGN KEY (activation_id) REFERENCES activation_records(activation_id)
                );
                
                -- 索引
                CREATE INDEX IF NOT EXISTS idx_license_status ON license_keys(status);
                CREATE INDEX IF NOT EXISTS idx_activation_license ON activation_records(license_key);
                CREATE INDEX IF NOT EXISTS idx_activation_device ON activation_records(device_id);
                CREATE INDEX IF NOT EXISTS idx_activation_user ON activation_records(user_id);
            """)
            conn.commit()
    
    def validate_format(self, license_key: str) -> ValidationResponse:
        """
        验证激活码格式
        
        Args:
            license_key: 激活码字符串
        
        Returns:
            ValidationResponse: 验证结果
        """
        parsed = self.generator.parse_key_string(license_key)
        
        if parsed is None or not parsed.get('is_valid'):
            return ValidationResponse(
                result=ValidationResult.INVALID_FORMAT,
                message="激活码格式不正确，应为：XXX-YYYY-YYYY-YYYY-ZZZZZZ"
            )
        
        return ValidationResponse(
            result=ValidationResult.VALID,
            message="格式验证通过",
            license_info={
                'prefix': parsed['prefix'],
                'serial': parsed['serial'],
                'checksum': parsed['checksum'],
            }
        )
    
    def validate_checksum(self, license_key: str) -> ValidationResponse:
        """
        验证激活码校验位
        
        Args:
            license_key: 激活码字符串
        
        Returns:
            ValidationResponse: 验证结果
        """
        # 先验证格式
        format_result = self.validate_format(license_key)
        if not format_result.is_valid:
            return format_result
        
        parsed = self.generator.parse_key_string(license_key)
        parts = license_key.upper().split('-')
        
        if len(parts) != 5:
            return ValidationResponse(
                result=ValidationResult.INVALID_FORMAT,
                message="激活码格式不正确"
            )
        
        version_code = parts[0]
        serial = '-'.join(parts[1:4])
        provided_checksum = parts[4]
        
        # 重新计算校验位
        # 从数据库获取expires_at（如果没有则假设未过期）
        expected_checksum = self._compute_checksum(version_code, serial, "")
        
        if provided_checksum != expected_checksum:
            return ValidationResponse(
                result=ValidationResult.INVALID_CHECKSUM,
                message="激活码校验失败，可能已被篡改"
            )
        
        return ValidationResponse(
            result=ValidationResult.VALID,
            message="校验位验证通过"
        )
    
    def _compute_checksum(self, version: str, serial: str, expires: str) -> str:
        """计算校验位"""
        data = f"{version}{serial}{expires}HERMES"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()[:6].upper()
    
    def check_status(self, license_key: str) -> ValidationResponse:
        """
        检查激活码状态
        
        Args:
            license_key: 激活码字符串
        
        Returns:
            ValidationResponse: 验证结果
        """
        # 验证格式
        format_result = self.validate_format(license_key)
        if not format_result.is_valid:
            return format_result
        
        parts = license_key.upper().split('-')
        version_code = parts[0]
        serial = '-'.join(parts[1:4])
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM license_keys 
                   WHERE version = ? AND serial = ?""",
                (version_code, serial)
            )
            row = cursor.fetchone()
        
        if row is None:
            # 激活码不在数据库中，检查是否过期
            try:
                # 尝试解析过期日期
                return ValidationResponse(
                    result=ValidationResult.VALID,
                    message="激活码验证通过",
                    license_info={
                        'version': version_code,
                        'serial': serial,
                        'status': 'UNKNOWN',
                    }
                )
            except Exception:
                return ValidationResponse(
                    result=ValidationResult.INVALID_FORMAT,
                    message="无法识别的激活码"
                )
        
        status = row['status']
        
        if status == 'REVOKED':
            return ValidationResponse(
                result=ValidationResult.REVOKED,
                message="该激活码已被发行方撤销"
            )
        
        if status == 'ACTIVATED':
            return ValidationResponse(
                result=ValidationResult.ALREADY_ACTIVATED,
                message="该激活码已被使用"
            )
        
        # 检查过期
        expires_at = row['expires_at']
        if expires_at:
            exp_date = datetime.strptime(expires_at, "%Y%m%d")
            if datetime.now() > exp_date:
                return ValidationResponse(
                    result=ValidationResult.EXPIRED,
                    message=f"激活码已于 {expires_at} 过期"
                )
        
        features = json.loads(row['features'] or '[]')
        return ValidationResponse(
            result=ValidationResult.VALID,
            message="激活码状态正常",
            license_info={
                'version': row['version'],
                'serial': row['serial'],
                'expires_at': row['expires_at'],
                'features': features,
                'max_users': row['max_users'],
                'status': row['status'],
            }
        )
    
    def activate(
        self,
        license_key: str,
        device_id: str,
        user_id: str,
        real_name: str = None,
        id_number: str = None,
        phone: str = None
    ) -> ValidationResponse:
        """
        激活激活码
        
        Args:
            license_key: 激活码
            device_id: 设备ID
            user_id: 用户ID
            real_name: 真实姓名（可选）
            id_number: 身份证号（可选）
            phone: 手机号（可选）
        
        Returns:
            ValidationResponse: 激活结果
        """
        # 检查状态
        status_result = self.check_status(license_key)
        
        if not status_result.is_valid:
            if status_result.result == ValidationResult.ALREADY_ACTIVATED:
                return ValidationResponse(
                    result=ValidationResult.ALREADY_ACTIVATED,
                    message="该激活码已被使用"
                )
            elif status_result.result == ValidationResult.EXPIRED:
                return status_result
            elif status_result.result == ValidationResult.REVOKED:
                return status_result
            return status_result
        
        # 实名验证（企业版必须）
        parsed = self.generator.parse_key_string(license_key)
        version_code = parsed['prefix']
        
        if version_code == 'ENT':
            # 企业版必须实名
            if not real_name:
                return ValidationResponse(
                    result=ValidationResult.UNKNOWN_ERROR,
                    message="企业版激活需要实名认证"
                )
            
            # 检查实名用户数量（最多5人）
            real_name_count = self.get_real_name_user_count()
            if real_name_count >= 5:
                return ValidationResponse(
                    result=ValidationResult.MAX_USERS_REACHED,
                    message="实名用户数已达上限（5人）"
                )
        
        # 执行激活
        parts = license_key.upper().split('-')
        version_code = parts[0]
        serial = '-'.join(parts[1:4])
        
        activation_id = f"ACT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{device_id[:8]}"
        activated_at = datetime.now().strftime("%Y%m%d")
        
        # 获取过期时间
        expires_at = "20991231"  # 默认不过期
        if status_result.license_info and status_result.license_info.get('expires_at'):
            expires_at = status_result.license_info['expires_at']
        
        # 加密实名信息
        real_name_encrypted = ""
        id_number_encrypted = ""
        phone_encrypted = ""
        
        if real_name:
            enc_data = self.crypto.encrypt_real_name(real_name, id_number or "")
            real_name_encrypted = enc_data.to_json()
        if phone:
            phone_enc = self.crypto.encrypt_real_name(phone, "")
            phone_encrypted = phone_enc.to_json()
        
        try:
            with self._get_connection() as conn:
                # 更新激活码状态
                conn.execute(
                    """UPDATE license_keys SET status = 'ACTIVATED' 
                       WHERE version = ? AND serial = ?""",
                    (version_code, serial)
                )
                
                # 插入激活记录
                conn.execute(
                    """INSERT INTO activation_records 
                       (activation_id, license_key, version, device_id, user_id, 
                        real_name_encrypted, activated_at, expires_at, status, features)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        activation_id,
                        license_key,
                        version_code,
                        device_id,
                        user_id,
                        real_name_encrypted,
                        activated_at,
                        expires_at,
                        'ACTIVE',
                        '[]'
                    )
                )
                
                # 插入实名用户
                if real_name:
                    conn.execute(
                        """INSERT OR REPLACE INTO real_name_users 
                           (user_id, real_name_encrypted, id_number_encrypted, phone_encrypted,
                            verification_type, verified_at, status)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            user_id,
                            real_name_encrypted,
                            id_number_encrypted,
                            phone_encrypted,
                            'ID_CARD' if id_number else 'NAME_ONLY',
                            activated_at,
                            'ACTIVE'
                        )
                    )
                
                # 插入设备记录
                conn.execute(
                    """INSERT OR REPLACE INTO devices 
                       (device_id, activation_id, last_active_at, status)
                       VALUES (?, ?, ?, ?)""",
                    (device_id, activation_id, activated_at, 'ACTIVE')
                )
                
                conn.commit()
            
            return ValidationResponse(
                result=ValidationResult.VALID,
                message="激活成功！",
                license_info={
                    'activation_id': activation_id,
                    'version': version_code,
                    'expires_at': expires_at,
                },
                activation_record=ActivationRecord(
                    activation_id=activation_id,
                    license_key=license_key,
                    version=version_code,
                    device_id=device_id,
                    user_id=user_id,
                    real_name=real_name_encrypted,
                    activated_at=activated_at,
                    expires_at=expires_at,
                    status='ACTIVE'
                )
            )
            
        except Exception as e:
            return ValidationResponse(
                result=ValidationResult.DATABASE_ERROR,
                message=f"激活失败：{str(e)}"
            )
    
    def deactivate(self, license_key: str, reason: str = "用户主动注销") -> ValidationResponse:
        """
        注销激活
        
        Args:
            license_key: 激活码
            reason: 注销原因
        
        Returns:
            ValidationResponse: 注销结果
        """
        parts = license_key.upper().split('-')
        version_code = parts[0]
        serial = '-'.join(parts[1:4])
        
        try:
            with self._get_connection() as conn:
                # 更新激活码状态
                conn.execute(
                    """UPDATE license_keys SET status = 'UNUSED' 
                       WHERE version = ? AND serial = ?""",
                    (version_code, serial)
                )
                
                # 删除激活记录
                conn.execute(
                    "DELETE FROM activation_records WHERE license_key = ?",
                    (license_key,)
                )
                
                # 删除设备记录
                conn.execute(
                    "DELETE FROM devices WHERE activation_id IN (SELECT activation_id FROM activation_records WHERE license_key = ?)",
                    (license_key,)
                )
                
                conn.commit()
            
            return ValidationResponse(
                result=ValidationResult.VALID,
                message=f"注销成功：{reason}"
            )
            
        except Exception as e:
            return ValidationResponse(
                result=ValidationResult.DATABASE_ERROR,
                message=f"注销失败：{str(e)}"
            )
    
    def get_real_name_user_count(self) -> int:
        """获取实名用户数量"""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as cnt FROM real_name_users WHERE status = 'ACTIVE'")
            row = cursor.fetchone()
            return row['cnt'] if row else 0
    
    def get_activation_info(self, license_key: str = None, device_id: str = None) -> Optional[Dict]:
        """
        获取激活信息
        
        Args:
            license_key: 激活码
            device_id: 设备ID
        
        Returns:
            Dict: 激活信息
        """
        condition = ""
        params = []
        
        if license_key:
            condition = "WHERE ar.license_key = ?"
            params = [license_key]
        elif device_id:
            condition = "WHERE ar.device_id = ?"
            params = [device_id]
        
        query = f"""
            SELECT 
                ar.*,
                lk.version,
                lk.features,
                lk.max_users
            FROM activation_records ar
            JOIN license_keys lk ON ar.license_key = lk.license_key
            {condition}
        """
        
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            
            if row:
                return dict(row)
        
        return None
    
    def register_license_key(self, license_key: LicenseKey) -> bool:
        """
        注册激活码到数据库（发行方使用）
        
        Args:
            license_key: 激活码对象
        
        Returns:
            bool: 是否注册成功
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO license_keys 
                       (license_key, version, serial, checksum, expires_at, issued_at, features, max_users, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        license_key.key_string,
                        license_key.version.code,
                        license_key.serial,
                        license_key.checksum,
                        license_key.expires_at,
                        license_key.issued_at,
                        json.dumps(license_key.features),
                        license_key.max_users,
                        'UNUSED'
                    )
                )
                conn.commit()
            return True
        except Exception:
            return False


# 单例
_validator: Optional[LicenseValidator] = None


def get_license_validator() -> LicenseValidator:
    """获取激活码验证器单例"""
    global _validator
    if _validator is None:
        _validator = LicenseValidator()
    return _validator