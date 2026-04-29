"""
用户认证与实名体系模块

功能：
1. 多级实名认证（匿名/基础/完全/企业）
2. 手机号认证
3. 身份证认证
4. 人脸识别认证
5. 分级数据加密存储
6. 实名凭证管理
7. 用户同意管理
8. 认证进度奖励
"""

import json
import re
import uuid
import hashlib
import time
import secrets
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from pathlib import Path
import asyncio


# ============ 枚举定义 ============

class AuthLevel(Enum):
    """认证级别"""
    ANONYMOUS = 0           # 匿名用户
    BASIC_VERIFIED = 1      # 基础实名（手机号）
    REAL_NAME = 2           # 完全实名（身份证）
    ENTERPRISE = 3         # 企业认证


class VerificationChannel(Enum):
    """认证渠道"""
    PHONE = "phone"                     # 手机号
    ID_CARD = "id_card"                 # 身份证
    FACE_RECOGNITION = "face"          # 人脸识别
    ALIPAY = "alipay"                   # 支付宝
    WECHAT = "wechat"                   # 微信
    BANK = "bank"                       # 银行
    GOVERNMENT = "government"           # 公安部


class UserStatus(Enum):
    """用户状态"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class ConsentStatus(Enum):
    """同意状态"""
    PENDING = "pending"
    AGREED = "agreed"
    REJECTED = "rejected"


# ============ 数据模型 ============

@dataclass
class User:
    """用户"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    nickname: str = ""

    # 认证级别
    auth_level: int = AuthLevel.ANONYMOUS.value
    auth_levels_history: Dict[str, str] = field(default_factory=dict)  # {level: verified_at}

    # 基本信息
    phone: str = ""
    email: str = ""

    # 实名信息
    real_name: str = ""
    id_card_masked: str = ""  # 脱敏身份证号
    id_card_hash: str = ""    # 身份证哈希（用于验证）

    # 企业信息
    enterprise_name: str = ""
    enterprise_license: str = ""  # 营业执照
    enterprise_verified: bool = False

    # 状态
    status: str = UserStatus.ACTIVE.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_login_at: Optional[str] = None

    # 设置
    avatar_url: str = ""
    settings: Dict = field(default_factory=dict)

    # 认证信息
    verification_channels: List[str] = field(default_factory=list)
    credential_token: str = ""  # 实名凭证token

    # 功能解锁
    unlocked_features: List[str] = field(default_factory=list)
    badges: List[str] = field(default_factory=list)

    def get_auth_level_name(self) -> str:
        """获取认证级别名称"""
        names = {
            0: "匿名用户",
            1: "基础实名",
            2: "完全实名",
            3: "企业认证"
        }
        return names.get(self.auth_level, "未知")

    def has_feature(self, feature: str) -> bool:
        """检查是否有某功能权限"""
        return self.auth_level >= self._get_feature_required_level(feature)

    def _get_feature_required_level(self, feature: str) -> int:
        """获取功能所需认证级别"""
        feature_requirements = {
            "create_form": 1,
            "workflow_approval": 2,
            "data_export": 2,
            "team_management": 3,
            "api_access": 3
        }
        return feature_requirements.get(feature, 0)


@dataclass
class VerificationCode:
    """验证码"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    phone: str = ""
    code: str = ""
    purpose: str = "verify"  # verify/login/register
    expires_at: str = ""
    verified: bool = False
    verified_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RealNameCredential:
    """实名凭证"""
    credential_id: str = ""
    user_id: str = ""

    # 凭证信息
    real_name: str = ""
    id_card_masked: str = ""
    auth_level: int = 0

    # 认证信息
    verification_channel: str = ""
    verification_time: str = ""
    expire_time: str = ""

    # 签名
    signature: str = ""
    issuer: str = "SmartRoute Platform"
    version: str = "1.0"

    def is_expired(self) -> bool:
        """检查是否过期"""
        expire_dt = datetime.fromisoformat(self.expire_time)
        return datetime.now() > expire_dt


@dataclass
class Consent:
    """用户同意"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""

    consent_id: str = ""
    consent_name: str = ""
    consent_type: str = ""  # user_agreement/privacy_policy/biometric

    # 同意状态
    status: str = ConsentStatus.AGREED.value
    agreed_at: Optional[str] = None

    # 版本
    version: str = "1.0"
    version_required: str = "1.0"

    # IP等信息
    ip_address: str = ""
    user_agent: str = ""


@dataclass
class AuthReward:
    """认证奖励"""
    level: int = 0
    badge: str = ""
    features: List[str] = field(default_factory=list)
    storage_quota: str = ""  # e.g., "+1GB"


# ============ 认证奖励配置 ============

AUTH_REWARDS = {
    AuthLevel.BASIC_VERIFIED.value: AuthReward(
        level=1,
        badge="📱 手机验证者",
        features=["custom_theme", "basic_form_templates"],
        storage_quota="+1GB"
    ),
    AuthLevel.REAL_NAME.value: AuthReward(
        level=2,
        badge="🆔 实名用户",
        features=["workflow_create", "data_export", "advanced_templates"],
        storage_quota="+5GB"
    ),
    AuthLevel.ENTERPRISE.value: AuthReward(
        level=3,
        badge="🏢 企业用户",
        features=["team_collaboration", "api_access", "priority_support"],
        storage_quota="unlimited"
    )
}


# ============ 用户存储 ============

class SecureUserStore:
    """安全用户存储"""

    def __init__(self, store_path: str = None):
        if store_path is None:
            store_path = Path("~/.hermes/user_auth").expanduser()

        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

        # 子目录
        self.users_dir = self.store_path / "users"
        self.credentials_dir = self.store_path / "credentials"
        self.consents_dir = self.store_path / "consents"
        self.verification_codes_dir = self.store_path / "verification_codes"

        for d in [self.users_dir, self.credentials_dir, self.consents_dir, self.verification_codes_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 索引
        self._users_index = self.store_path / "users.json"
        self._consents_index = self.store_path / "consents.json"

        self._load_indexes()

    def _load_indexes(self):
        """加载索引"""
        if self._users_index.exists():
            with open(self._users_index, "r", encoding="utf-8") as f:
                self._users_index_data: Dict[str, dict] = json.load(f)
        else:
            self._users_index_data = {}

        if self._consents_index.exists():
            with open(self._consents_index, "r", encoding="utf-8") as f:
                self._consents_index_data: List[dict] = json.load(f)
        else:
            self._consents_index_data = []

    def _save_users_index(self):
        """保存用户索引"""
        with open(self._users_index, "w", encoding="utf-8") as f:
            json.dump(self._users_index_data, f, ensure_ascii=False, indent=2)

    def _save_consents_index(self):
        """保存同意索引"""
        with open(self._consents_index, "w", encoding="utf-8") as f:
            json.dump(self._consents_index_data, f, ensure_ascii=False, indent=2)

    # ============ 用户操作 ============

    def save_user(self, user: User) -> str:
        """保存用户"""
        user.updated_at = datetime.now().isoformat()

        user_file = self.users_dir / f"{user.id}.json"
        with open(user_file, "w", encoding="utf-8") as f:
            json.dump(asdict(user), f, ensure_ascii=False, indent=2)

        self._users_index_data[user.id] = {
            "username": user.username,
            "phone": user.phone,
            "auth_level": user.auth_level,
            "status": user.status
        }
        self._save_users_index()

        return user.id

    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户"""
        user_file = self.users_dir / f"{user_id}.json"
        if not user_file.exists():
            return None

        with open(user_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return User(**data)

    def get_user_by_phone(self, phone: str) -> Optional[User]:
        """通过手机号获取用户"""
        for user_id in self._users_index_data:
            user = self.get_user(user_id)
            if user and user.phone == phone:
                return user
        return None

    def get_user_by_username(self, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        for user_id, data in self._users_index_data.items():
            if data.get("username") == username:
                return self.get_user(user_id)
        return None

    def list_users(self) -> List[User]:
        """列出所有用户"""
        users = []
        for user_id in self._users_index_data:
            user = self.get_user(user_id)
            if user:
                users.append(user)
        return users

    def update_auth_level(self, user_id: str, new_level: int) -> bool:
        """更新认证级别"""
        user = self.get_user(user_id)
        if not user:
            return False

        user.auth_level = new_level
        user.auth_levels_history[str(new_level)] = datetime.now().isoformat()

        # 解锁功能
        reward = AUTH_REWARDS.get(new_level)
        if reward:
            for feature in reward.features:
                if feature not in user.unlocked_features:
                    user.unlocked_features.append(feature)
            if reward.badge not in user.badges:
                user.badges.append(reward.badge)

        self.save_user(user)
        return True

    # ============ 凭证操作 ============

    def save_credential(self, credential: RealNameCredential):
        """保存实名凭证"""
        cred_file = self.credentials_dir / f"{credential.credential_id}.json"
        with open(cred_file, "w", encoding="utf-8") as f:
            json.dump(asdict(credential), f, ensure_ascii=False, indent=2)

    def get_credential(self, credential_id: str) -> Optional[RealNameCredential]:
        """获取凭证"""
        cred_file = self.credentials_dir / f"{credential_id}.json"
        if not cred_file.exists():
            return None

        with open(cred_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return RealNameCredential(**data)

    # ============ 同意操作 ============

    def save_consent(self, consent: Consent):
        """保存同意记录"""
        consent_file = self.consents_dir / f"{consent.id}.json"
        with open(consent_file, "w", encoding="utf-8") as f:
            json.dump(asdict(consent), f, ensure_ascii=False, indent=2)

        self._consents_index_data.append({
            "id": consent.id,
            "user_id": consent.user_id,
            "consent_id": consent.consent_id
        })
        self._save_consents_index()

    def get_user_consents(self, user_id: str) -> List[Consent]:
        """获取用户的所有同意记录"""
        consents = []

        for consent_meta in self._consents_index_data:
            if consent_meta["user_id"] == user_id:
                consent_file = self.consents_dir / f"{consent_meta['id']}.json"
                if consent_file.exists():
                    with open(consent_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    consents.append(Consent(**data))

        return consents

    # ============ 验证码操作 ============

    def save_verification_code(self, code: VerificationCode):
        """保存验证码"""
        code_file = self.verification_codes_dir / f"{code.id}.json"
        with open(code_file, "w", encoding="utf-8") as f:
            json.dump(asdict(code), f, ensure_ascii=False, indent=2)

    def get_verification_code(self, code_id: str) -> Optional[VerificationCode]:
        """获取验证码"""
        code_file = self.verification_codes_dir / f"{code_id}.json"
        if not code_file.exists():
            return None

        with open(code_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return VerificationCode(**data)

    def get_valid_code_by_phone(self, phone: str, purpose: str = "verify") -> Optional[VerificationCode]:
        """获取有效的验证码"""
        for code_file in self.verification_codes_dir.glob("*.json"):
            with open(code_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            code = VerificationCode(**data)
            if (code.phone == phone and
                code.purpose == purpose and
                not code.verified and
                datetime.now() < datetime.fromisoformat(code.expires_at)):
                return code

        return None


# ============ 认证服务 ============

class RealNameAuthService:
    """实名认证服务"""

    def __init__(self, store: SecureUserStore):
        self.store = store

        # 认证渠道（实际会调用外部API）
        self._channels = {
            VerificationChannel.PHONE.value: self._verify_phone,
            VerificationChannel.ID_CARD.value: self._verify_id_card,
        }

    # ============ 手机号认证 ============

    async def verify_phone(self, phone: str) -> tuple:
        """发送验证码到手机号"""
        # 1. 格式验证
        if not self._validate_phone_format(phone):
            return False, "手机号格式错误"

        # 2. 生成验证码
        code = self._generate_code()

        # 3. 存储验证码
        expires = datetime.now() + timedelta(minutes=10)
        verification = VerificationCode(
            phone=phone,
            code=code,
            purpose="verify",
            expires_at=expires.isoformat()
        )
        self.store.save_verification_code(verification)

        # 4. 发送短信（模拟）
        await self._send_sms(phone, code)

        return True, verification.id

    async def confirm_phone_code(self, verification_id: str, code: str) -> tuple:
        """确认手机验证码"""
        verification = self.store.get_verification_code(verification_id)
        if not verification:
            return False, "验证码不存在"

        if verification.verified:
            return False, "验证码已使用"

        if datetime.now() > datetime.fromisoformat(verification.expires_at):
            return False, "验证码已过期"

        if verification.code != code:
            return False, "验证码错误"

        # 标记已验证
        verification.verified = True
        verification.verified_at = datetime.now().isoformat()
        self.store.save_verification_code(verification)

        return True, verification.phone

    async def complete_phone_verification(self, user_id: str, phone: str) -> tuple:
        """完成手机号认证"""
        user = self.store.get_user(user_id)
        if not user:
            return False, "用户不存在"

        # 绑定手机号
        user.phone = phone
        user.verification_channels.append(VerificationChannel.PHONE.value)

        # 如果是首次认证，升级到基础实名
        if user.auth_level < AuthLevel.BASIC_VERIFIED.value:
            self.store.update_auth_level(user_id, AuthLevel.BASIC_VERIFIED.value)

        return True, "认证成功"

    # ============ 身份证认证 ============

    async def verify_id_card(
        self,
        user_id: str,
        real_name: str,
        id_card: str,
        face_image: bytes = None
    ) -> tuple:
        """验证身份证信息"""
        # 1. 格式验证
        if not self._validate_id_card_format(id_card):
            return False, "身份证格式错误"

        # 2. 脱敏存储
        id_card_masked = self._mask_id_card(id_card)
        id_card_hash = hashlib.sha256(id_card.encode()).hexdigest()

        # 3. 选择认证渠道并验证
        channel = await self._select_verification_channel()
        verified = await self._call_verification_api(
            channel,
            real_name=real_name,
            id_card=id_card
        )

        if not verified:
            return False, "身份证信息验证失败"

        # 4. 人脸比对（如果提供）
        if face_image:
            face_match = await self._verify_face(face_image, id_card)
            if not face_match:
                return False, "人脸比对失败"

        # 5. 生成实名凭证
        credential = RealNameCredential(
            credential_id=str(uuid.uuid4()),
            user_id=user_id,
            real_name=real_name,
            id_card_masked=id_card_masked,
            auth_level=AuthLevel.REAL_NAME.value,
            verification_channel=channel,
            verification_time=datetime.now().isoformat(),
            expire_time=(datetime.now() + timedelta(days=365)).isoformat()
        )
        credential.signature = self._sign_credential(credential)
        self.store.save_credential(credential)

        # 6. 更新用户信息
        user = self.store.get_user(user_id)
        if user:
            user.real_name = real_name
            user.id_card_masked = id_card_masked
            user.id_card_hash = id_card_hash
            user.credential_token = credential.credential_id
            user.verification_channels.append(VerificationChannel.ID_CARD.value)
            user.credential_token = credential.credential_id

            # 升级到完全实名
            if user.auth_level < AuthLevel.REAL_NAME.value:
                self.store.update_auth_level(user_id, AuthLevel.REAL_NAME.value)

        return True, "认证成功"

    # ============ 人脸识别 ============

    async def verify_face(self, user_id: str, live_image: bytes) -> tuple:
        """活体检测和人脸验证"""
        # 1. 活体检测
        liveness_result = await self._detect_liveness(live_image)
        if not liveness_result["success"]:
            return False, "活体检测失败"

        # 2. 获取用户的身份证照片
        user = self.store.get_user(user_id)
        if not user or not user.credential_token:
            return False, "用户未完成身份证认证"

        credential = self.store.get_credential(user.credential_token)
        if not credential:
            return False, "凭证不存在"

        # 3. 人脸比对
        face_match = await self._compare_faces(live_image, credential.id_card_masked)
        if not face_match:
            return False, "人脸比对失败"

        # 4. 添加人脸识别认证
        user.verification_channels.append(VerificationChannel.FACE_RECOGNITION.value)
        self.store.save_user(user)

        return True, "认证成功"

    # ============ 工具方法 ============

    def _validate_phone_format(self, phone: str) -> bool:
        """验证手机号格式"""
        pattern = r"^1[3-9]\d{9}$"
        return bool(re.match(pattern, phone))

    def _validate_id_card_format(self, id_card: str) -> bool:
        """验证身份证格式"""
        pattern = r"^\d{17}[\dXx]$"
        return bool(re.match(pattern, id_card))

    def _mask_id_card(self, id_card: str) -> str:
        """脱敏身份证号"""
        if len(id_card) == 18:
            return id_card[:6] + "********" + id_card[-4:]
        return id_card[:4] + "****" + id_card[-4:]

    def _mask_phone(self, phone: str) -> str:
        """脱敏手机号"""
        return phone[:3] + "****" + phone[-4:]

    def _generate_code(self, length: int = 6) -> str:
        """生成验证码"""
        return "".join([str(secrets.randbelow(10)) for _ in range(length)])

    async def _send_sms(self, phone: str, code: str):
        """发送短信（实际会调用短信API）"""
        print(f"[SMS] Sending code {code} to {phone}")
        # 实际实现会调用短信网关
        await asyncio.sleep(0.1)

    async def _select_verification_channel(self) -> str:
        """选择认证渠道"""
        # 优先使用政府API
        return VerificationChannel.GOVERNMENT.value

    async def _call_verification_api(
        self,
        channel: str,
        real_name: str,
        id_card: str
    ) -> bool:
        """调用认证API"""
        # 实际实现会调用外部API
        # 这里模拟验证通过
        print(f"[VERIFY] Calling {channel} API for {real_name}")
        await asyncio.sleep(0.5)
        return True

    async def _detect_liveness(self, image: bytes) -> dict:
        """活体检测"""
        # 实际实现会调用活体检测API
        await asyncio.sleep(0.3)
        return {"success": True, "confidence": 0.95}

    async def _verify_face(self, live_image: bytes, id_card_masked: str) -> bool:
        """人脸验证"""
        # 实际实现会调用人脸比对API
        await asyncio.sleep(0.3)
        return True

    async def _compare_faces(self, live_image: bytes, id_card_info: str) -> bool:
        """比对两张人脸"""
        await asyncio.sleep(0.3)
        return True

    def _sign_credential(self, credential: RealNameCredential) -> str:
        """签名凭证"""
        data = f"{credential.credential_id}:{credential.user_id}:{credential.verification_time}"
        return hashlib.sha256(data.encode()).hexdigest()


# ============ 同意管理 ============

class ConsentManager:
    """用户同意管理"""

    # 必需的同意项
    REQUIRED_CONSENTS = {
        "user_agreement": {
            "name": "用户服务协议",
            "type": "user_agreement",
            "required": True,
            "current_version": "1.2"
        },
        "privacy_policy": {
            "name": "隐私政策",
            "type": "privacy_policy",
            "required": True,
            "current_version": "1.3"
        },
        "phone_consent": {
            "name": "手机号使用授权",
            "type": "phone_consent",
            "required": True,
            "current_version": "1.0"
        },
        "real_name_consent": {
            "name": "实名信息使用授权",
            "type": "real_name_consent",
            "required": True,
            "current_version": "1.0"
        },
        "biometric_consent": {
            "name": "生物特征信息授权",
            "type": "biometric_consent",
            "required": True,
            "current_version": "1.0"
        }
    }

    def __init__(self, store: SecureUserStore):
        self.store = store

    def get_required_consents(self, auth_level: int) -> List[dict]:
        """获取需要的同意项"""
        consents = []

        # 所有人都需要基础同意
        consents.append(self.REQUIRED_CONSENTS["user_agreement"])
        consents.append(self.REQUIRED_CONSENTS["privacy_policy"])

        # 基础实名需要手机同意
        if auth_level >= AuthLevel.BASIC_VERIFIED.value:
            consents.append(self.REQUIRED_CONSENTS["phone_consent"])

        # 完全实名需要实名同意
        if auth_level >= AuthLevel.REAL_NAME.value:
            consents.append(self.REQUIRED_CONSENTS["real_name_consent"])

        # 人脸识别需要生物特征同意
        if auth_level >= AuthLevel.REAL_NAME.value:
            consents.append(self.REQUIRED_CONSENTS["biometric_consent"])

        return consents

    def get_pending_consents(self, user_id: str) -> List[dict]:
        """获取待处理的同意项"""
        user_consents = self.store.get_user_consents(user_id)
        agreed_ids = {c.consent_id for c in user_consents if c.status == ConsentStatus.AGREED.value}

        pending = []
        for consent_def in self.REQUIRED_CONSENTS.values():
            if consent_def["consent_id"] not in agreed_ids:
                pending.append(consent_def)

        return pending

    async def record_consent(
        self,
        user_id: str,
        consent_id: str,
        agreed: bool,
        ip_address: str = "",
        user_agent: str = ""
    ) -> bool:
        """记录用户同意"""
        consent_def = self.REQUIRED_CONSENTS.get(consent_id)
        if not consent_def:
            return False

        if agreed and consent_def["required"]:
            consent = Consent(
                user_id=user_id,
                consent_id=consent_id,
                consent_name=consent_def["name"],
                consent_type=consent_def["type"],
                status=ConsentStatus.AGREED.value,
                agreed_at=datetime.now().isoformat(),
                version=consent_def["current_version"],
                ip_address=ip_address,
                user_agent=user_agent
            )
            self.store.save_consent(consent)
            return True

        return False


# ============ 主用户认证类 ============

class UserAuthManager:
    """用户认证管理器"""

    def __init__(self, store_path: str = None):
        self.store = SecureUserStore(store_path)
        self.auth_service = RealNameAuthService(self.store)
        self.consent_manager = ConsentManager(self.store)

        # 当前用户会话
        self.current_user_id: Optional[str] = None
        self.current_user: Optional[User] = None

    def create_user(
        self,
        username: str = "",
        nickname: str = "",
        phone: str = ""
    ) -> User:
        """创建用户"""
        user = User(
            username=username,
            nickname=nickname or username,
            phone=phone
        )
        self.store.save_user(user)
        return user

    def login(self, identifier: str, auth_type: str = "phone") -> Optional[User]:
        """登录"""
        user = None

        if auth_type == "phone":
            user = self.store.get_user_by_phone(identifier)
        elif auth_type == "username":
            user = self.store.get_user_by_username(identifier)

        if user:
            user.last_login_at = datetime.now().isoformat()
            self.store.save_user(user)
            self.current_user_id = user.id
            self.current_user = user

        return user

    def logout(self):
        """登出"""
        self.current_user_id = None
        self.current_user = None

    def get_current_user(self) -> Optional[User]:
        """获取当前用户"""
        if self.current_user_id and not self.current_user:
            self.current_user = self.store.get_user(self.current_user_id)
        return self.current_user

    def require_auth_level(self, required_level: int) -> tuple:
        """检查认证级别"""
        user = self.get_current_user()
        if not user:
            return False, "用户未登录"

        if user.auth_level < required_level:
            return False, f"需要认证级别{required_level}，当前为{user.auth_level}"

        return True, "OK"

    def get_auth_status_card(self) -> dict:
        """获取认证状态卡片"""
        user = self.get_current_user()
        if not user:
            return {"error": "用户未登录"}

        current_level = user.auth_level
        reward = AUTH_REWARDS.get(current_level)

        # 计算进度
        total_levels = 4
        progress_percentage = int((current_level / total_levels) * 100)

        return {
            "user_id": user.id,
            "level": current_level,
            "level_name": user.get_auth_level_name(),
            "badge": reward.badge if reward else "",
            "progress_percentage": progress_percentage,
            "badges": user.badges,
            "unlocked_features": user.unlocked_features,
            "verification_channels": user.verification_channels,
            "next_level": current_level + 1 if current_level < 3 else None
        }

    async def grant_reward(self, user_id: str, new_level: int) -> dict:
        """授予认证奖励"""
        reward = AUTH_REWARDS.get(new_level)
        if not reward:
            return {"success": False, "error": "无效的认证级别"}

        user = self.store.get_user(user_id)
        if not user:
            return {"success": False, "error": "用户不存在"}

        # 授予奖励
        for feature in reward.features:
            if feature not in user.unlocked_features:
                user.unlocked_features.append(feature)

        if reward.badge not in user.badges:
            user.badges.append(reward.badge)

        self.store.save_user(user)

        return {
            "success": True,
            "badge": reward.badge,
            "features": reward.features,
            "storage_quota": reward.storage_quota
        }


# ============ 全局实例 ============

_auth_manager: Optional[UserAuthManager] = None


def get_auth_manager() -> UserAuthManager:
    """获取认证管理器"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = UserAuthManager()
    return _auth_manager