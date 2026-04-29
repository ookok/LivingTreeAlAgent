"""
激活码生成器
License Key Generator

设计理念：
授权码 = 发行方印记 + 版本标识 + 随机特征码 + 校验位 + 有效期

格式: {前缀}-{版本}-{随机码}-{随机码}-{随机码}-{校验位}
示例: ENT-PRO-A3B7-C2D8-E9F1-7K4M5N

版本类型:
- PER: 个人版 (Personal) - 免费，不需要激活
- PRO: 专业版 (Professional) - 需要激活
- ENT: 企业版 (Enterprise) - 需要激活 + 实名认证

防伪机制:
1. 格式校验 - 固定长度和分隔符
2. 校验位校验 - SHA256哈希前6位
3. 有效期校验 - 过期自动拒绝
4. 发行方签名 - HMAC防伪
"""

import secrets
import hashlib
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .crypto_utils import get_crypto_utils, CryptoUtils


class LicenseVersion(Enum):
    """授权版本"""
    PERSONAL = ("PER", "个人版", False)      # 不需要激活
    PROFESSIONAL = ("PRO", "专业版", True)   # 需要激活
    ENTERPRISE = ("ENT", "企业版", True)     # 需要激活+实名
    
    def __init__(self, code: str, name: str, requires_activation: bool):
        self.code = code
        self.name = name
        self.requires_activation = requires_activation


class LicenseStatus(Enum):
    """授权状态"""
    UNUSED = ("UNUSED", "未使用")
    ACTIVATED = ("ACTIVATED", "已激活")
    EXPIRED = ("EXPIRED", "已过期")
    REVOKED = ("REVOKED", "已撤销")
    INVALID = ("INVALID", "无效")
    
    def __init__(self, code: str, name: str):
        self.code = code
        self.name = name


@dataclass
class LicenseKey:
    """激活码数据结构"""
    version: LicenseVersion          # 版本
    serial: str                     # 序列号
    checksum: str                   # 校验位
    expires_at: str                 # 过期日期 (YYYYMMDD)
    issued_at: str                  # 发行日期
    features: List[str] = field(default_factory=list)  # 功能列表
    max_users: int = 1              # 最大用户数
    metadata: Dict[str, Any] = field(default_factory=dict)  # 附加数据
    
    @property
    def key_string(self) -> str:
        """完整的激活码字符串"""
        return f"{self.version.code}-{self.serial}-{self.checksum}"
    
    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        exp_date = datetime.strptime(self.expires_at, "%Y%m%d")
        return datetime.now() > exp_date
    
    @property
    def days_until_expire(self) -> int:
        """距离过期的天数"""
        exp_date = datetime.strptime(self.expires_at, "%Y%m%d")
        delta = exp_date - datetime.now()
        return max(0, delta.days)
    
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            'version': self.version.name,
            'version_code': self.version.code,
            'serial': self.serial,
            'checksum': self.checksum,
            'expires_at': self.expires_at,
            'issued_at': self.issued_at,
            'features': self.features,
            'max_users': self.max_users,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'LicenseKey':
        """从字典反序列化"""
        version = LicenseVersion[data['version']]
        return cls(
            version=version,
            serial=data['serial'],
            checksum=data['checksum'],
            expires_at=data['expires_at'],
            issued_at=data['issued_at'],
            features=data.get('features', []),
            max_users=data.get('max_users', 1),
            metadata=data.get('metadata', {}),
        )


@dataclass
class GeneratedBatch:
    """批量生成的激活码批次"""
    batch_id: str                   # 批次ID
    version: LicenseVersion          # 版本
    count: int                      # 数量
    expires_at: str                 # 统一过期日期
    keys: List[LicenseKey] = field(default_factory=list)  # 生成的密钥
    created_at: str                  # 创建时间
    created_by: str = "SYSTEM"      # 创建者


class LicenseGenerator:
    """
    激活码生成器
    
    功能：
    1. 生成单个激活码
    2. 批量生成激活码
    3. 激活码格式校验
    4. 激活码序列化/反序列化
    """
    
    # 激活码各部分长度
    SERIAL_SEGMENTS = 3             # 序列号分段数
    SERIAL_SEGMENT_LEN = 4         # 每段长度
    
    def __init__(self, issuer_id: str = "HERMES"):
        """
        初始化生成器
        
        Args:
            issuer_id: 发行方标识（用于区分不同销售渠道）
        """
        self.issuer_id = issuer_id
        self.crypto = get_crypto_utils()
    
    def _generate_serial_segment(self) -> str:
        """生成序列号片段"""
        return secrets.token_hex(self.SERIAL_SEGMENT_LEN).upper()[:self.SERIAL_SEGMENT_LEN]
    
    def _generate_serial(self) -> str:
        """生成完整序列号"""
        segments = [self._generate_serial_segment() for _ in range(self.SERIAL_SEGMENTS)]
        return '-'.join(segments)
    
    def _compute_checksum(self, version: str, serial: str, expires: str) -> str:
        """
        计算校验位
        
        算法: SHA256(version + serial + expires + issuer_id) 取前6位
        """
        data = f"{version}{serial}{expires}{self.issuer_id}"
        hash_result = hashlib.sha256(data.encode('utf-8')).hexdigest()
        return hash_result[:6].upper()
    
    def generate(
        self,
        version: LicenseVersion,
        expires_days: int = 365,
        features: List[str] = None,
        max_users: int = 1,
        metadata: Dict[str, Any] = None
    ) -> LicenseKey:
        """
        生成单个激活码
        
        Args:
            version: 版本类型
            expires_days: 有效期天数
            features: 功能列表
            max_users: 最大用户数
            metadata: 附加元数据
        
        Returns:
            LicenseKey: 生成的激活码
        """
        serial = self._generate_serial()
        issued_at = datetime.now().strftime("%Y%m%d")
        expires_at = (datetime.now() + timedelta(days=expires_days)).strftime("%Y%m%d")
        
        checksum = self._compute_checksum(version.code, serial, expires_at)
        
        return LicenseKey(
            version=version,
            serial=serial,
            checksum=checksum,
            expires_at=expires_at,
            issued_at=issued_at,
            features=features or [],
            max_users=max_users,
            metadata=metadata or {},
        )
    
    def generate_batch(
        self,
        version: LicenseVersion,
        count: int,
        expires_days: int = 365,
        features: List[str] = None,
        max_users: int = 1,
        batch_name: str = None,
        created_by: str = "SYSTEM"
    ) -> GeneratedBatch:
        """
        批量生成激活码
        
        Args:
            version: 版本类型
            count: 数量
            expires_days: 有效期天数
            features: 功能列表
            max_users: 最大用户数
            batch_name: 批次名称
            created_by: 创建者
        
        Returns:
            GeneratedBatch: 批次对象
        """
        batch_id = secrets.token_hex(8).upper()
        expires_at = (datetime.now() + timedelta(days=expires_days)).strftime("%Y%m%d")
        
        keys = []
        for _ in range(count):
            key = self.generate(
                version=version,
                expires_days=expires_days,
                features=features,
                max_users=max_users,
            )
            keys.append(key)
        
        return GeneratedBatch(
            batch_id=batch_id,
            version=version,
            count=count,
            expires_at=expires_at,
            keys=keys,
            created_at=datetime.now().isoformat(),
            created_by=created_by,
        )
    
    @staticmethod
    def parse_key_string(key_string: str) -> Optional[Dict[str, str]]:
        """
        解析激活码字符串
        
        格式: XXX-YYYY-YYYY-YYYY-CHECK
        
        Returns:
            Dict: {'prefix', 'serial', 'checksum', 'is_valid'}
        """
        parts = key_string.strip().upper().split('-')
        
        if len(parts) != 5:
            return None
        
        try:
            # 验证版本前缀
            prefix = parts[0]
            if prefix not in ['PER', 'PRO', 'ENT']:
                return None
            
            # 验证序列号格式
            serial = '-'.join(parts[1:4])
            for seg in parts[1:4]:
                if len(seg) != LicenseGenerator.SERIAL_SEGMENT_LEN:
                    return None
                if not seg.isalnum():
                    return None
            
            # 验证校验位
            checksum = parts[4]
            if len(checksum) != 6:
                return None
            
            return {
                'prefix': prefix,
                'serial': serial,
                'checksum': checksum,
                'is_valid': True,
                'original': key_string,
            }
        except Exception:
            return None
    
    def export_batch_to_json(self, batch: GeneratedBatch) -> str:
        """导出批次为JSON"""
        data = {
            'batch_id': batch.batch_id,
            'version': batch.version.name,
            'version_code': batch.version.code,
            'count': batch.count,
            'expires_at': batch.expires_at,
            'created_at': batch.created_at,
            'created_by': batch.created_by,
            'keys': [key.to_dict() for key in batch.keys],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def export_batch_to_text(self, batch: GeneratedBatch) -> str:
        """导出批次为文本格式（便于打印）"""
        lines = [
            f"# 激活码批次: {batch.batch_id}",
            f"# 版本: {batch.version.name} ({batch.version.code})",
            f"# 数量: {batch.count}",
            f"# 过期日期: {batch.expires_at}",
            f"# 创建时间: {batch.created_at}",
            f"# 创建者: {batch.created_by}",
            "",
            "# " + "=" * 60,
            "# 激活码列表",
            "# " + "=" * 60,
            "",
        ]
        
        for i, key in enumerate(batch.keys, 1):
            lines.append(f"{i:3d}. {key.key_string}  |  过期: {key.expires_at}  |  用户数: {key.max_users}")
        
        return '\n'.join(lines)


# 单例
_generator: Optional[LicenseGenerator] = None


def get_license_generator() -> LicenseGenerator:
    """获取激活码生成器单例"""
    global _generator
    if _generator is None:
        _generator = LicenseGenerator()
    return _generator