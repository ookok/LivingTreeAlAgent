"""
Enterprise License Service - 企业许可证服务
==========================================

提供企业序列号生成、验证和注册功能。

流程：
1. 客户端对企业名称生成 8 位码
2. 序列号生成器验证 8 位码后生成序列号
3. 用户拿到序列号后与 8 位码进行校验
4. 通过校验后企业信息注册成功
5. 每次登录企业模式都要校验序列号

Author: Hermes Desktop Team
"""

import os
import re
import uuid
import hashlib
import time
import secrets
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path


# ============ 枚举定义 ============

class LicenseType(Enum):
    """许可证类型"""
    TRIAL = "trial"           # 试用版
    STANDARD = "standard"     # 标准版
    PROFESSIONAL = "professional"  # 专业版
    ENTERPRISE = "enterprise" # 企业版


class LicenseStatus(Enum):
    """许可证状态"""
    ACTIVE = "active"        # 激活
    EXPIRED = "expired"       # 过期
    REVOKED = "revoked"       # 撤销
    SUSPENDED = "suspended"   # 暂停


# ============ 数据模型 ============

@dataclass
class EnterpriseInfo:
    """企业信息"""
    enterprise_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    enterprise_name: str = ""
    enterprise_code: str = ""  # 8位码
    license_type: str = LicenseType.STANDARD.value
    status: str = LicenseStatus.ACTIVE.value
    
    # 许可证信息
    serial_number: str = ""
    license_key: str = ""  # 激活密钥
    
    # 时间戳
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    registered_at: Optional[str] = None
    expires_at: Optional[str] = None
    last_verified_at: Optional[str] = None
    
    # 设备信息
    registered_device_id: str = ""
    device_fingerprint: str = ""
    
    # 统计
    verify_count: int = 0
    max_verify_count: int = 100  # 最大验证次数


@dataclass
class LicenseRecord:
    """许可证记录"""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    enterprise_id: str = ""
    serial_number: str = ""
    
    # 操作信息
    action: str = ""  # generate/validate/register/verify/revoke
    ip_address: str = ""
    device_fingerprint: str = ""
    user_agent: str = ""
    
    # 结果
    success: bool = False
    error_message: str = ""
    
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ============ 许可证存储 ============

class LicenseStore:
    """许可证存储"""
    
    def __init__(self, store_path: str = None):
        if store_path is None:
            store_path = Path("~/.hermes/license").expanduser()
        
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)
        
        # 子目录
        self.enterprises_dir = self.store_path / "enterprises"
        self.records_dir = self.store_path / "records"
        self.codes_dir = self.store_path / "codes"  # 8位码临时存储
        
        for d in [self.enterprises_dir, self.records_dir, self.codes_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # 索引
        self._enterprises_index = self.store_path / "enterprises.json"
        self._codes_index = self.store_path / "codes.json"
        
        self._load_indexes()
    
    def _load_indexes(self):
        """加载索引"""
        if self._enterprises_index.exists():
            with open(self._enterprises_index, "r", encoding="utf-8") as f:
                self._enterprises_index_data: Dict[str, dict] = json.load(f)
        else:
            self._enterprises_index_data = {}
        
        if self._codes_index.exists():
            with open(self._codes_index, "r", encoding="utf-8") as f:
                self._codes_index_data: Dict[str, dict] = json.load(f)
        else:
            self._codes_index_data = {}
    
    def _save_enterprises_index(self):
        """保存企业索引"""
        with open(self._enterprises_index, "w", encoding="utf-8") as f:
            json.dump(self._enterprises_index_data, f, ensure_ascii=False, indent=2)
    
    def _save_codes_index(self):
        """保存码索引"""
        with open(self._codes_index, "w", encoding="utf-8") as f:
            json.dump(self._codes_index_data, f, ensure_ascii=False, indent=2)
    
    # ============ 企业操作 ============
    
    def save_enterprise(self, enterprise: EnterpriseInfo) -> str:
        """保存企业信息"""
        enterprise.updated_at = datetime.now().isoformat()
        
        ent_file = self.enterprises_dir / f"{enterprise.enterprise_id}.json"
        with open(ent_file, "w", encoding="utf-8") as f:
            json.dump(asdict(enterprise), f, ensure_ascii=False, indent=2)
        
        # 更新索引
        self._enterprises_index_data[enterprise.enterprise_id] = {
            "enterprise_name": enterprise.enterprise_name,
            "enterprise_code": enterprise.enterprise_code,
            "serial_number": enterprise.serial_number,
            "status": enterprise.status
        }
        self._save_enterprises_index()
        
        return enterprise.enterprise_id
    
    def get_enterprise(self, enterprise_id: str) -> Optional[EnterpriseInfo]:
        """获取企业信息"""
        ent_file = self.enterprises_dir / f"{enterprise_id}.json"
        if not ent_file.exists():
            return None
        
        with open(ent_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return EnterpriseInfo(**data)
    
    def get_enterprise_by_code(self, enterprise_code: str) -> Optional[EnterpriseInfo]:
        """通过8位码获取企业"""
        for ent_id, data in self._enterprises_index_data.items():
            if data.get("enterprise_code", "").upper() == enterprise_code.upper():
                return self.get_enterprise(ent_id)
        return None
    
    def get_enterprise_by_serial(self, serial_number: str) -> Optional[EnterpriseInfo]:
        """通过序列号获取企业"""
        for ent_id, data in self._enterprises_index_data.items():
            if data.get("serial_number", "") == serial_number:
                return self.get_enterprise(ent_id)
        return None
    
    def get_enterprise_by_name(self, enterprise_name: str) -> Optional[EnterpriseInfo]:
        """通过名称获取企业"""
        for ent_id, data in self._enterprises_index_data.items():
            if data.get("enterprise_name", "") == enterprise_name:
                return self.get_enterprise(ent_id)
        return None
    
    # ============ 8位码操作 ============
    
    def save_code(self, enterprise_code: str, enterprise_name: str, expires_minutes: int = 30) -> str:
        """保存8位码（临时）"""
        code_id = str(uuid.uuid4())
        code_data = {
            "code_id": code_id,
            "enterprise_code": enterprise_code.upper(),
            "enterprise_name": enterprise_name,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(minutes=expires_minutes)).isoformat(),
            "used": False
        }
        
        code_file = self.codes_dir / f"{code_id}.json"
        with open(code_file, "w", encoding="utf-8") as f:
            json.dump(code_data, f, ensure_ascii=False, indent=2)
        
        self._codes_index_data[code_id] = {
            "enterprise_code": enterprise_code.upper(),
            "enterprise_name": enterprise_name,
            "expires_at": code_data["expires_at"]
        }
        self._save_codes_index()
        
        return code_id
    
    def get_code(self, code_id: str) -> Optional[Dict[str, Any]]:
        """获取码信息"""
        code_file = self.codes_dir / f"{code_id}.json"
        if not code_file.exists():
            return None
        
        with open(code_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def mark_code_used(self, code_id: str):
        """标记码已使用"""
        code_data = self.get_code(code_id)
        if code_data:
            code_data["used"] = True
            code_file = self.codes_dir / f"{code_id}.json"
            with open(code_file, "w", encoding="utf-8") as f:
                json.dump(code_data, f, ensure_ascii=False, indent=2)
    
    # ============ 记录操作 ============
    
    def save_record(self, record: LicenseRecord):
        """保存操作记录"""
        record_file = self.records_dir / f"{record.record_id}.json"
        with open(record_file, "w", encoding="utf-8") as f:
            json.dump(asdict(record), f, ensure_ascii=False, indent=2)
    
    def get_records_by_enterprise(self, enterprise_id: str) -> list:
        """获取企业的所有记录"""
        records = []
        for record_file in self.records_dir.glob("*.json"):
            with open(record_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("enterprise_id") == enterprise_id:
                    records.append(LicenseRecord(**data))
        return records


# ============ 企业许可证服务 ============

class EnterpriseLicenseService:
    """企业许可证服务"""
    
    # 算法常量
    CODE_LENGTH = 8
    SERIAL_LENGTH = 19  # XXXX-XXXX-XXXX-XXXX
    
    def __init__(self, store: LicenseStore = None):
        self.store = store or LicenseStore()
    
    # ============ 客户端：生成8位码 ============
    
    @staticmethod
    def generate_enterprise_code(enterprise_name: str) -> str:
        """
        客户端：对企业名称生成8位码
        
        算法：
        1. 企业名称 SHA256 哈希
        2. 取前8位转为大写
        3. 添加校验位
        """
        if not enterprise_name or len(enterprise_name.strip()) < 2:
            raise ValueError("企业名称至少需要2个字符")
        
        # 规范化名称（去除空格、转小写）
        normalized = enterprise_name.strip().lower()
        
        # SHA256 哈希
        hash_value = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        
        # 取前8位
        code_base = hash_value[:self.CODE_LENGTH].upper()
        
        # 计算校验位（确保码的校验性）
        checksum = sum(ord(c) for c in normalized) % 26 + 65
        checksum_char = chr(checksum)
        
        # 插入校验位（最后一位）
        code = code_base[:-1] + checksum_char
        
        return code
    
    @staticmethod
    def verify_enterprise_code(enterprise_name: str, code: str) -> bool:
        """客户端：验证8位码"""
        expected = EnterpriseLicenseService.generate_enterprise_code(enterprise_name)
        return expected.upper() == code.upper()
    
    # ============ 服务端：生成序列号 ============
    
    def generate_serial_number(
        self,
        enterprise_code: str,
        enterprise_name: str,
        license_type: str = LicenseType.STANDARD.value,
        expires_days: int = 365
    ) -> Tuple[str, str]:
        """
        服务端：生成序列号
        
        Returns:
            (serial_number, license_key)
        """
        # 1. 验证8位码
        if not self.verify_enterprise_code(enterprise_name, enterprise_code):
            raise ValueError("8位码验证失败，请检查企业名称")
        
        # 2. 检查企业是否已注册
        existing = self.store.get_enterprise_by_name(enterprise_name)
        if existing and existing.serial_number:
            raise ValueError("该企业已注册序列号")
        
        # 3. 生成序列号
        # 格式: XXXX-XXXX-XXXX-XXXX
        # XXXX: 企业码前4位
        # XXXX: 时间戳（hex）
        # XXXX: 随机数
        # XXXX: 校验码
        
        timestamp_part = int(time.time()).to_bytes(8, "big").hex()[:8].upper()
        random_part = secrets.token_hex(4)[:8].upper()
        
        # 校验码 = 企业码 + 时间戳前4位 的 SHA256 前4位
        check_input = f"{enterprise_code}{timestamp_part}".encode()
        checksum_part = hashlib.sha256(check_input).hexdigest()[:8].upper()
        
        serial_number = (
            f"{enterprise_code[:4].upper()}-"
            f"{timestamp_part[:4]}-"
            f"{random_part[:4]}-"
            f"{checksum_part[:4]}"
        )
        
        # 4. 生成激活密钥
        license_key_raw = f"{serial_number}{enterprise_code}{int(time.time())}"
        license_key = hashlib.sha256(license_key_raw.encode()).hexdigest()[:32].upper()
        license_key = "-".join([license_key[i:i+4] for i in range(0, 32, 4)])
        
        # 5. 创建企业信息
        enterprise_id = str(uuid.uuid4())
        enterprise = EnterpriseInfo(
            enterprise_id=enterprise_id,
            enterprise_name=enterprise_name,
            enterprise_code=enterprise_code.upper(),
            serial_number=serial_number,
            license_key=license_key,
            license_type=license_type,
            status=LicenseStatus.ACTIVE.value,
            created_at=datetime.now().isoformat(),
            expires_at=(datetime.now() + timedelta(days=expires_days)).isoformat()
        )
        
        self.store.save_enterprise(enterprise)
        
        # 6. 记录操作
        self._record_action(
            enterprise_id=enterprise_id,
            action="generate",
            success=True,
            details={"license_type": license_type}
        )
        
        return serial_number, license_key
    
    # ============ 服务端：验证序列号 ============
    
    def validate_serial(
        self,
        serial_number: str,
        enterprise_code: str,
        enterprise_name: str,
        device_fingerprint: str = ""
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        服务端：验证序列号
        
        Returns:
            (success, message, enterprise_info)
        """
        # 1. 格式验证
        if not self._validate_serial_format(serial_number):
            return False, "序列号格式错误", {}
        
        # 2. 验证8位码
        if not self.verify_enterprise_code(enterprise_name, enterprise_code):
            return False, "8位码验证失败", {}
        
        # 3. 查找企业
        enterprise = self.store.get_enterprise_by_serial(serial_number)
        if not enterprise:
            return False, "序列号未注册", {}
        
        # 4. 验证企业名称
        if enterprise.enterprise_name != enterprise_name:
            return False, "企业名称不匹配", {}
        
        # 5. 验证企业码
        if enterprise.enterprise_code != enterprise_code.upper():
            return False, "企业码不匹配", {}
        
        # 6. 检查状态
        if enterprise.status != LicenseStatus.ACTIVE.value:
            return False, f"许可证状态异常: {enterprise.status}", {}
        
        # 7. 检查过期
        if enterprise.expires_at:
            expires_dt = datetime.fromisoformat(enterprise.expires_at)
            if datetime.now() > expires_dt:
                return False, "许可证已过期", {}
        
        # 8. 检查验证次数
        if enterprise.verify_count >= enterprise.max_verify_count:
            return False, "验证次数超限", {}
        
        # 9. 更新验证信息
        enterprise.verify_count += 1
        enterprise.last_verified_at = datetime.now().isoformat()
        if device_fingerprint:
            enterprise.device_fingerprint = device_fingerprint
        self.store.save_enterprise(enterprise)
        
        # 10. 记录操作
        self._record_action(
            enterprise_id=enterprise.enterprise_id,
            action="validate",
            success=True,
            details={"device_fingerprint": device_fingerprint}
        )
        
        return True, "验证成功", asdict(enterprise)
    
    # ============ 服务端：注册/激活 ============
    
    def register_enterprise(
        self,
        serial_number: str,
        enterprise_code: str,
        enterprise_name: str,
        device_fingerprint: str = "",
        license_key: str = ""
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        服务端：注册企业（激活许可证）
        
        这是用户拿到序列号后的注册步骤
        """
        # 1. 验证序列号
        success, msg, enterprise = self.validate_serial(
            serial_number, enterprise_code, enterprise_name, device_fingerprint
        )
        
        if not success:
            return False, msg, {}
        
        # 2. 验证激活密钥（如果有）
        if license_key and enterprise.get("license_key"):
            if license_key != enterprise["license_key"]:
                return False, "激活密钥错误", {}
        
        # 3. 更新注册信息
        ent = self.store.get_enterprise(enterprise["enterprise_id"])
        ent.registered_at = datetime.now().isoformat()
        ent.registered_device_id = device_fingerprint or str(uuid.uuid4())
        self.store.save_enterprise(ent)
        
        # 4. 记录操作
        self._record_action(
            enterprise_id=ent.enterprise_id,
            action="register",
            success=True,
            details={"device_fingerprint": device_fingerprint}
        )
        
        return True, "注册成功", asdict(ent)
    
    # ============ 服务端：登录验证 ============
    
    def verify_on_login(
        self,
        serial_number: str,
        enterprise_code: str,
        enterprise_name: str,
        device_fingerprint: str = ""
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        服务端：登录时验证许可证
        
        企业模式每次登录都需要调用此方法
        """
        # 1. 验证序列号
        success, msg, enterprise = self.validate_serial(
            serial_number, enterprise_code, enterprise_name, device_fingerprint
        )
        
        if not success:
            return False, msg, {}
        
        # 2. 检查是否已注册
        ent = self.store.get_enterprise(enterprise["enterprise_id"])
        if not ent.registered_at:
            return False, "许可证未激活，请先注册", {}
        
        # 3. 检查设备是否匹配（如果已绑定）
        if ent.device_fingerprint and device_fingerprint:
            if ent.device_fingerprint != device_fingerprint:
                # 允许新设备注册，但记录警告
                self._record_action(
                    enterprise_id=ent.enterprise_id,
                    action="verify",
                    success=True,
                    details={"warning": "device_mismatch", "new_device": device_fingerprint}
                )
        
        return True, "验证成功", asdict(ent)
    
    # ============ 服务端：撤销许可证 ============
    
    def revoke_license(self, serial_number: str, reason: str = "") -> Tuple[bool, str]:
        """撤销许可证"""
        enterprise = self.store.get_enterprise_by_serial(serial_number)
        if not enterprise:
            return False, "序列号不存在"
        
        enterprise.status = LicenseStatus.REVOKED.value
        self.store.save_enterprise(enterprise)
        
        self._record_action(
            enterprise_id=enterprise.enterprise_id,
            action="revoke",
            success=True,
            details={"reason": reason}
        )
        
        return True, "许可证已撤销"
    
    # ============ 工具方法 ============
    
    def _validate_serial_format(self, serial: str) -> bool:
        """验证序列号格式"""
        if not serial:
            return False
        
        # 格式: XXXX-XXXX-XXXX-XXXX
        pattern = r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$"
        return bool(re.match(pattern, serial.upper()))
    
    def _record_action(
        self,
        enterprise_id: str,
        action: str,
        success: bool,
        details: Dict[str, Any] = None,
        ip_address: str = "",
        user_agent: str = ""
    ):
        """记录操作"""
        record = LicenseRecord(
            enterprise_id=enterprise_id,
            serial_number="",
            action=action,
            success=success,
            error_message=details.get("error", "") if isinstance(details, dict) else "",
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.store.save_record(record)
    
    def get_license_info(self, serial_number: str) -> Tuple[bool, Dict[str, Any]]:
        """获取许可证信息（不验证）"""
        enterprise = self.store.get_enterprise_by_serial(serial_number)
        if not enterprise:
            return False, {}
        
        return True, {
            "enterprise_name": enterprise.enterprise_name,
            "license_type": enterprise.license_type,
            "status": enterprise.status,
            "created_at": enterprise.created_at,
            "expires_at": enterprise.expires_at,
            "registered_at": enterprise.registered_at
        }


# ============ 全局实例 ============

_license_service: Optional[EnterpriseLicenseService] = None


def get_license_service() -> EnterpriseLicenseService:
    """获取许可证服务单例"""
    global _license_service
    if _license_service is None:
        _license_service = EnterpriseLicenseService()
    return _license_service