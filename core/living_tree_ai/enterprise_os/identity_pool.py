"""
政府身份池管理

管理企业在各政府系统的登录凭证，实现单点登录。

核心功能：
1. 身份凭证安全存储
2. 登录状态管理
3. 自动登录调度
4. 登录历史追踪
"""

import json
import hashlib
import base64
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime, timedelta


# ==================== 数据模型 ====================

class GovSystemType(Enum):
    """政府系统类型"""
    MARKET_SUPERVISION = "market_supervision"     # 市场监管（工商）
    TAX = "tax"                                  # 税务
    ENVIRONMENT = "environment"                  # 环保
    SAFETY = "safety"                           # 应急/安全
    HUMAN_RESOURCE = "human_resource"            # 人社
    STATISTICS = "statistics"                    # 统计
    CUSTOMS = "customs"                          # 海关
    INTELLECTUAL_PROPERTY = "ip"               # 知识产权
    FINANCE = "finance"                          # 金融/商务
    OTHER = "other"                              # 其他


class LoginStatus(Enum):
    """登录状态"""
    IDLE = "idle"                                # 空闲
    LOGGING_IN = "logging_in"                    # 登录中
    ACTIVE = "active"                           # 已登录
    EXPIRED = "expired"                         # 已过期
    FAILED = "failed"                           # 登录失败
    LOCKED = "locked"                           # 账号锁定


@dataclass
class GovSystemAccount:
    """政府系统账号"""
    account_id: str
    profile_id: str                              # 关联的企业Profile
    system_type: GovSystemType
    system_name: str                             # 系统显示名称
    system_code: str                             # 系统代码（用于适配器匹配）

    # 凭证（加密存储）
    username: str
    encrypted_password: str                     # 加密后的密码
    additional_creds: Dict[str, str] = field(default_factory=dict)  # 额外凭证（U盾等）

    # 登录信息
    login_url: str
    home_url: str = ""                          # 登录后首页

    # 状态
    status: LoginStatus = LoginStatus.IDLE
    last_login: Optional[datetime] = None
    last_attempt: Optional[datetime] = None
    login_failures: int = 0                      # 连续失败次数
    session_token: str = ""                     # 当前会话Token
    session_expires: Optional[datetime] = None

    # 登录方式
    login_method: str = "password"               # password/certificate/sms/oauth
    requires_captcha: bool = False
    requires_otp: bool = False                  # 需要OTP
    otp_secret: str = ""

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class LoginAttempt:
    """登录尝试记录"""
    attempt_id: str
    account_id: str
    timestamp: datetime
    method: str                                 # login/captcha/otp/resume
    success: bool
    error_message: str = ""
    duration_ms: int = 0                        # 耗时毫秒
    ip_address: str = ""


# ==================== 内置政府系统配置 ====================

BUILTIN_GOV_SYSTEMS = {
    "国家市场监督管理总局": {
        "type": GovSystemType.MARKET_SUPERVISION,
        "code": "samr",
        "login_url": "https://zwfw.samr.gov.cn",
        "requires_captcha": True,
        "features": ["business_license", "annual_report", "electronic_signature"]
    },
    "国家税务总局电子税务局": {
        "type": GovSystemType.TAX,
        "code": "etax",
        "login_url": "https://etax.chinatax.gov.cn",
        "requires_captcha": True,
        "requires_otp": False,
        "features": ["tax_declaration", "invoice", "query"]
    },
    "全国排污许可管理信息平台": {
        "type": GovSystemType.ENVIRONMENT,
        "code": "permit_epi",
        "login_url": "https://permit.mee.gov.cn",
        "requires_captcha": True,
        "features": ["pollution_permit", "eia", "monitoring"]
    },
    "环境影响评价信用平台": {
        "type": GovSystemType.ENVIRONMENT,
        "code": "eia_credit",
        "login_url": "https://reeis.reees.ac.cn",
        "requires_captcha": True,
        "features": ["eia_registration", "eia_project"]
    },
    "国家企业信用信息公示系统": {
        "type": GovSystemType.MARKET_SUPERVISION,
        "code": "credit_info",
        "login_url": "https://www.gsxt.gov.cn",
        "requires_captcha": True,
        "features": ["credit_info", "search"]
    },
    "人力资源和社会保障部": {
        "type": GovSystemType.HUMAN_RESOURCE,
        "code": "mohrss",
        "login_url": "https://www.12333.gov.cn",
        "requires_captcha": False,
        "features": ["social_security", "employment"]
    },
    "全国统计联网直报平台": {
        "type": GovSystemType.STATISTICS,
        "code": "stats_report",
        "login_url": "https://stats.shenzhen.cn",
        "requires_captcha": True,
        "features": ["monthly_report", "annual_report"]
    },
    "中国海关企业进出口信用信息平台": {
        "type": GovSystemType.CUSTOMS,
        "code": "customs",
        "login_url": "http://credit.customs.gov.cn",
        "requires_captcha": True,
        "features": ["credit_info", "declaration"]
    },
    "中国专利公布公告网": {
        "type": GovSystemType.INTELLECTUAL_PROPERTY,
        "code": "patent_cnipa",
        "login_url": "https://cpquery.cponline.cnipa.gov.cn",
        "requires_captcha": False,
        "features": ["patent_search", "status"]
    },
    "中国商标网": {
        "type": GovSystemType.INTELLECTUAL_PROPERTY,
        "code": "trademark_saic",
        "login_url": "https://sbj.cnipa.gov.cn",
        "requires_captcha": False,
        "features": ["trademark_search", "apply"]
    }
}


# ==================== 加密工具 ====================

class CredentialEncryptor:
    """
    凭证加密器

    使用AES-256-GCM进行安全加密
    """

    def __init__(self, master_key: str = None):
        """
        Args:
            master_key: 主密钥（实际应从密钥管理服务获取）
        """
        import os
        # 实际应用中应从KMS获取主密钥
        self._master_key = master_key or os.urandom(32)

    def encrypt(self, plaintext: str) -> str:
        """
        加密凭证

        Returns:
            Base64编码的加密字符串
        """
        import os
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        aesgcm = AESGCM(self._master_key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)

        # 返回 nonce + ciphertext 的base64
        return base64.b64encode(nonce + ciphertext).decode()

    def decrypt(self, encrypted: str) -> str:
        """
        解密凭证

        Args:
            encrypted: Base64编码的加密字符串

        Returns:
            明文
        """
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        data = base64.b64decode(encrypted)
        nonce = data[:12]
        ciphertext = data[12:]

        aesgcm = AESGCM(self._master_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext.decode()


# ==================== 身份池管理器 ====================

class IdentityPoolManager:
    """
    政府身份池管理器

    核心功能：
    1. 管理企业在各政府系统的账号密码
    2. 维护登录状态和会话
    3. 提供自动登录接口
    4. 追踪登录历史
    """

    # 最大登录失败次数
    MAX_LOGIN_FAILURES = 5

    # 会话超时时间（分钟）
    SESSION_TIMEOUT_MINUTES = 30

    def __init__(self):
        self._accounts: Dict[str, GovSystemAccount] = {}  # account_id -> account
        self._profile_accounts: Dict[str, List[str]] = {}  # profile_id -> [account_ids]
        self._login_history: Dict[str, List[LoginAttempt]] = {}  # account_id -> attempts
        self._encryptor = CredentialEncryptor()

        # 加载内置系统配置
        self._systems = BUILTIN_GOV_SYSTEMS.copy()

    def register_system(
        self,
        system_name: str,
        system_type: GovSystemType,
        login_url: str,
        **kwargs
    ) -> str:
        """
        注册新的政府系统

        Args:
            system_name: 系统名称
            system_type: 系统类型
            login_url: 登录URL
            **kwargs: 其他配置

        Returns:
            system_code
        """
        system_code = kwargs.get("code", self._generate_system_code(system_name))
        self._systems[system_name] = {
            "type": system_type,
            "code": system_code,
            "login_url": login_url,
            **kwargs
        }
        return system_code

    async def add_account(
        self,
        profile_id: str,
        system_name: str,
        username: str,
        password: str,
        additional_creds: Dict = None,
        **kwargs
    ) -> str:
        """
        添加政府系统账号

        Args:
            profile_id: 企业Profile ID
            system_name: 系统名称
            username: 用户名
            password: 密码
            additional_creds: 额外凭证（如U盾密码）

        Returns:
            account_id
        """
        # 获取系统配置
        system_config = self._systems.get(system_name)
        if not system_config:
            raise ValueError(f"Unknown government system: {system_name}")

        # 生成账号ID
        account_id = self._generate_account_id(profile_id, system_config["code"])

        # 加密密码
        encrypted_password = self._encryptor.encrypt(password)

        # 创建账号
        account = GovSystemAccount(
            account_id=account_id,
            profile_id=profile_id,
            system_type=system_config["type"],
            system_name=system_name,
            system_code=system_config["code"],
            username=username,
            encrypted_password=encrypted_password,
            additional_creds=additional_creds or {},
            login_url=system_config["login_url"],
            requires_captcha=system_config.get("requires_captcha", False),
            requires_otp=system_config.get("requires_otp", False),
            otp_secret=kwargs.get("otp_secret", "")
        )

        # 存储
        self._accounts[account_id] = account

        # 更新profile索引
        if profile_id not in self._profile_accounts:
            self._profile_accounts[profile_id] = []
        self._profile_accounts[profile_id].append(account_id)

        return account_id

    async def get_account(self, account_id: str) -> Optional[GovSystemAccount]:
        """获取账号"""
        return self._accounts.get(account_id)

    async def get_account_by_system(
        self,
        profile_id: str,
        system_name: str
    ) -> Optional[GovSystemAccount]:
        """通过系统和Profile获取账号"""
        system_config = self._systems.get(system_name)
        if not system_config:
            return None

        account_id = self._generate_account_id(profile_id, system_config["code"])
        return self._accounts.get(account_id)

    async def get_profile_accounts(self, profile_id: str) -> List[GovSystemAccount]:
        """获取企业的所有政府系统账号"""
        account_ids = self._profile_accounts.get(profile_id, [])
        return [
            self._accounts[aid]
            for aid in account_ids
            if aid in self._accounts
        ]

    async def update_login_status(
        self,
        account_id: str,
        status: LoginStatus,
        session_token: str = None,
        error_message: str = None
    ) -> bool:
        """
        更新登录状态

        Args:
            account_id: 账号ID
            status: 新状态
            session_token: 会话Token（登录成功时）
            error_message: 错误信息

        Returns:
            是否成功
        """
        account = self._accounts.get(account_id)
        if not account:
            return False

        old_status = account.status
        account.status = status
        account.updated_at = datetime.now()

        if status == LoginStatus.ACTIVE:
            account.last_login = datetime.now()
            account.login_failures = 0
            account.session_token = session_token or ""
            account.session_expires = datetime.now() + timedelta(
                minutes=self.SESSION_TIMEOUT_MINUTES
            )
        elif status == LoginStatus.FAILED:
            account.login_failures += 1
            account.last_attempt = datetime.now()
            if account.login_failures >= self.MAX_LOGIN_FAILURES:
                account.status = LoginStatus.LOCKED

        # 记录尝试
        self._record_login_attempt(
            account_id,
            "login",
            status == LoginStatus.ACTIVE,
            error_message
        )

        return True

    async def is_session_valid(self, account_id: str) -> bool:
        """检查会话是否有效"""
        account = self._accounts.get(account_id)
        if not account:
            return False

        if account.status != LoginStatus.ACTIVE:
            return False

        if account.session_expires and datetime.now() > account.session_expires:
            account.status = LoginStatus.EXPIRED
            return False

        return True

    async def get_decrypted_password(self, account_id: str) -> Optional[str]:
        """获取解密后的密码（仅内部使用）"""
        account = self._accounts.get(account_id)
        if not account:
            return None

        try:
            return self._encryptor.decrypt(account.encrypted_password)
        except:
            return None

    async def get_login_url(self, account_id: str) -> Optional[str]:
        """获取登录URL"""
        account = self._accounts.get(account_id)
        return account.login_url if account else None

    async def get_system_config(self, system_name: str) -> Optional[Dict]:
        """获取系统配置"""
        return self._systems.get(system_name)

    async def list_registered_systems(self) -> List[Dict]:
        """列出所有注册的系统"""
        return [
            {
                "name": name,
                "code": config["code"],
                "type": config["type"].value,
                "login_url": config["login_url"],
                "features": config.get("features", [])
            }
            for name, config in self._systems.items()
        ]

    def _generate_account_id(self, profile_id: str, system_code: str) -> str:
        """生成账号ID"""
        raw = f"{profile_id}:{system_code}"
        return f"ACC:{hashlib.sha256(raw.encode()).hexdigest()[:16].upper()}"

    def _generate_system_code(self, system_name: str) -> str:
        """生成系统代码"""
        return hashlib.md5(system_name.encode()).hexdigest()[:8]

    def _record_login_attempt(
        self,
        account_id: str,
        method: str,
        success: bool,
        error_message: str = None,
        duration_ms: int = 0
    ):
        """记录登录尝试"""
        if account_id not in self._login_history:
            self._login_history[account_id] = []

        attempt = LoginAttempt(
            attempt_id=hashlib.md5(
                f"{account_id}:{time.time()}".encode()
            ).hexdigest()[:12],
            account_id=account_id,
            timestamp=datetime.now(),
            method=method,
            success=success,
            error_message=error_message or "",
            duration_ms=duration_ms
        )

        self._login_history[account_id].append(attempt)

        # 只保留最近100条记录
        if len(self._login_history[account_id]) > 100:
            self._login_history[account_id] = self._login_history[account_id][-100:]

    async def get_login_history(
        self,
        account_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """获取登录历史"""
        attempts = self._login_history.get(account_id, [])
        return [
            {
                "attempt_id": a.attempt_id,
                "timestamp": a.timestamp.isoformat(),
                "method": a.method,
                "success": a.success,
                "error_message": a.error_message,
                "duration_ms": a.duration_ms
            }
            for a in attempts[-limit:]
        ]


# ==================== 单例模式 ====================

_identity_pool: Optional[IdentityPoolManager] = None


def get_identity_pool() -> IdentityPoolManager:
    """获取身份池管理器单例"""
    global _identity_pool
    if _identity_pool is None:
        _identity_pool = IdentityPoolManager()
    return _identity_pool
