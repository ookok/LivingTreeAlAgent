"""
第2层：密钥处理器 (Key Processor Layer)
=======================================

功能：解密、验证、标准化密钥

核心能力：
1. 密钥类型自动检测
2. 格式验证与标准化
3. 在线有效性验证
4. 主密钥管理

Author: Hermes Desktop AI Assistant
"""

import os
import re
import base64
import hashlib
import hmac
import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class KeyType(Enum):
    """密钥类型枚举"""
    UNKNOWN = "unknown"
    API_KEY = "api_key"              # 普通API密钥
    OAUTH_TOKEN = "oauth_token"      # OAuth令牌
    BEARER_TOKEN = "bearer_token"    # Bearer令牌
    BASIC_AUTH = "basic_auth"        # Basic认证
    JWT_TOKEN = "jwt_token"          # JWT令牌
    AWS_ACCESS_KEY = "aws_access"    # AWS访问密钥
    AWS_SECRET_KEY = "aws_secret"    # AWS秘密密钥
    ENCRYPTED = "encrypted"         # 加密的密钥


class KeyFormat(Enum):
    """密钥格式枚举"""
    RAW = "raw"                      # 原始字符串
    BASE64 = "base64"                # Base64编码
    HEX = "hex"                      # 十六进制
    JSON = "json"                    # JSON格式
    ENCRYPTED_FERNET = "fernet"      # Fernet加密格式


@dataclass
class ProcessedKey:
    """
    处理后的密钥对象

    Attributes:
        provider: 提供商名称
        value: 密钥值（解密后）
        key_type: 密钥类型
        format: 原始格式
        is_valid: 是否有效
        validation_time: 最后验证时间
        expires_at: 过期时间（如果已知）
        source: 来源
        injected_at: 注入时间
        id: 唯一标识符
        rotation_needed: 是否需要轮转
        metadata: 额外元数据
    """
    provider: str
    value: str
    key_type: KeyType = KeyType.UNKNOWN
    format: KeyFormat = KeyFormat.RAW
    is_valid: bool = True
    validation_time: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    source: str = "unknown"
    injected_at: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: hashlib.sha256(str(datetime.now()).encode()).hexdigest()[:16])
    rotation_needed: bool = False
    metadata: Dict = field(default_factory=dict)

    def is_expired(self) -> bool:
        """检查密钥是否过期"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def days_until_expiry(self) -> Optional[int]:
        """距离过期的天数"""
        if self.expires_at is None:
            return None
        delta = self.expires_at - datetime.now()
        return delta.days

    def needs_rotation(self, threshold_days: int = 30) -> bool:
        """检查是否需要轮转"""
        if self.rotation_needed:
            return True
        if self.expires_at:
            return self.days_until_expiry() < threshold_days
        return False


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class KeyProcessor:
    """
    密钥处理器 - 解密、验证、标准化

    功能：
    1. 密钥类型自动检测
    2. 格式检测与转换
    3. 有效性验证（在线/离线）
    4. 主密钥管理
    5. 密钥指纹生成

    使用示例：
        processor = KeyProcessor()
        processed = processor.process_keys({'openai': 'sk-xxx', 'anthropic': 'sk-ant-xxx'})
    """

    # 常见API密钥的格式模式
    KEY_PATTERNS = {
        'openai': {
            'pattern': r'^sk-[A-Za-z0-9_-]{20,}$',
            'type': KeyType.API_KEY,
            'prefixes': ['sk-'],
        },
        'anthropic': {
            'pattern': r'^sk-ant-[A-Za-z0-9_-]{20,}$',
            'type': KeyType.API_KEY,
            'prefixes': ['sk-ant-'],
        },
        'azure_openai': {
            'pattern': r'^[A-Za-z0-9_-]{32,}$',
            'type': KeyType.API_KEY,
            'prefixes': [],
        },
        'google': {
            'pattern': r'^AIza[A-Za-z0-9_-]{35,}$',
            'type': KeyType.API_KEY,
            'prefixes': ['AIza'],
        },
        'aws_access': {
            'pattern': r'^AKIA[A-Z0-9]{16}$',
            'type': KeyType.AWS_ACCESS_KEY,
            'prefixes': ['AKIA'],
        },
        'aws_secret': {
            'pattern': r'^[A-Za-z0-9/+=]{40}$',
            'type': KeyType.AWS_SECRET_KEY,
            'prefixes': [],
        },
        'jwt': {
            'pattern': r'^eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$',
            'type': KeyType.JWT_TOKEN,
            'prefixes': ['eyJ'],
        },
        'bearer': {
            'pattern': r'^[A-Za-z0-9_-]+$',
            'type': KeyType.BEARER_TOKEN,
            'prefixes': [],
        },
    }

    # 已知过期时间的密钥类型
    KNOWN_EXPIRY = {
        'aws_access': 365,  # AWS Access Key 通常1年过期
        'jwt': 1,           # JWT 通常1天过期
    }

    def __init__(self, master_key: Optional[bytes] = None, config: Optional[Dict] = None):
        """
        初始化密钥处理器

        Args:
            master_key: 主密钥（用于解密加密的密钥）
            config: 可选配置
        """
        self.config = config or {}
        self.master_key = master_key or self._load_master_key()
        self.cipher = self._init_cipher()
        self._validation_cache: Dict[str, ValidationResult] = {}
        self._lock = threading.Lock()

        logger.info("KeyProcessor 初始化完成")

    def process_keys(self, raw_keys: Dict[str, str]) -> Dict[str, ProcessedKey]:
        """
        处理所有原始密钥

        Args:
            raw_keys: provider -> raw_key 的映射

        Returns:
            provider -> ProcessedKey 的映射
        """
        processed: Dict[str, ProcessedKey] = {}

        for provider, raw_key in raw_keys.items():
            try:
                processed_key = self._process_single_key(provider, raw_key)
                processed[provider] = processed_key
                logger.debug(f"处理密钥 {provider}: 类型={processed_key.key_type.value}, 有效={processed_key.is_valid}")
            except Exception as e:
                logger.error(f"处理密钥 {provider} 失败: {e}")
                # 创建一个无效的ProcessedKey记录错误
                processed[provider] = ProcessedKey(
                    provider=provider,
                    value="",
                    is_valid=False,
                    metadata={'error': str(e)}
                )

        return processed

    def _process_single_key(self, provider: str, raw_key: str) -> ProcessedKey:
        """
        处理单个密钥的完整流程

        1. 检测原始格式
        2. 检测密钥类型
        3. 解密（如需要）
        4. 验证格式
        5. 验证有效性
        6. 估算过期时间
        """
        # 1. 检测原始格式
        original_format = self._detect_format(raw_key)

        # 2. 检测密钥类型
        key_type = self._detect_key_type(provider, raw_key)

        # 3. 解密（如需要）
        decrypted_value = raw_key
        final_format = original_format

        if self._is_encrypted(raw_key):
            decrypted_value = self._decrypt_key(raw_key)
            final_format = KeyFormat.RAW

        # 4. 验证格式
        validation_result = self._validate_format(provider, decrypted_value, key_type)
        if not validation_result.is_valid:
            logger.warning(f"密钥 {provider} 格式验证失败: {validation_result.errors}")

        # 5. 在线验证（异步进行）
        is_valid = True  # 默认离线有效
        validation_time = datetime.now()

        if validation_result.is_valid and self._should_online_validate(key_type):
            is_valid = self._validate_key_online(provider, decrypted_value)
            validation_time = datetime.now()

        # 6. 估算过期时间
        expires_at = self._estimate_expiry(provider, key_type)

        # 7. 检查是否需要轮转
        rotation_needed = self._check_rotation_needed(provider, decrypted_value)

        return ProcessedKey(
            provider=provider,
            value=decrypted_value,
            key_type=key_type,
            format=final_format,
            is_valid=is_valid and validation_result.is_valid,
            validation_time=validation_time,
            expires_at=expires_at,
            source=self._get_key_source(provider),
            injected_at=datetime.now(),
            rotation_needed=rotation_needed,
            metadata=validation_result.metadata
        )

    def _load_master_key(self) -> bytes:
        """
        加载或生成主密钥

        优先级：
        1. 环境变量 ECO_MASTER_KEY
        2. 环境变量 HERMES_MASTER_KEY
        3. 文件 ~/.ecohub/master.key
        4. 自动生成新密钥
        """
        # 方案1：环境变量
        env_key = os.getenv('ECO_MASTER_KEY') or os.getenv('HERMES_MASTER_KEY')
        if env_key:
            if isinstance(env_key, str):
                # Base64解码或直接使用
                try:
                    return base64.urlsafe_b64decode(env_key)
                except Exception:
                    return env_key.encode()[:32].ljust(32, b'\0')
            return env_key[:32]

        # 方案2：文件加载
        key_path = os.path.expanduser('~/.ecohub/master.key')
        if os.path.exists(key_path):
            with open(key_path, 'rb') as f:
                return f.read()

        # 方案3：自动生成
        new_key = self._generate_master_key()
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        with open(key_path, 'wb') as f:
            f.write(new_key)
        os.chmod(key_path, 0o600)  # 仅当前用户可读写

        logger.warning("自动生成了新的主密钥，请妥善保存 ECO_MASTER_KEY 环境变量")
        return new_key

    def _generate_master_key(self) -> bytes:
        """生成新的主密钥"""
        from cryptography.fernet import Fernet
        return Fernet.generate_key()

    def _init_cipher(self):
        """初始化加密器"""
        from cryptography.fernet import Fernet
        return Fernet(self.master_key if len(self.master_key) == 44 else
                     base64.urlsafe_b64encode(self.master_key[:32].ljust(32, b'\0')))

    def _detect_format(self, raw_key: str) -> KeyFormat:
        """检测密钥原始格式"""
        # Base64
        if self._is_base64(raw_key):
            # 尝试解码验证
            try:
                decoded = base64.urlsafe_b64decode(raw_key)
                if len(decoded) in [16, 32]:
                    return KeyFormat.BASE64
            except Exception:
                pass

        # Hex
        if self._is_hex(raw_key) and len(raw_key) % 2 == 0:
            return KeyFormat.HEX

        # Fernet加密格式
        if raw_key.startswith('gAAAAA'):
            return KeyFormat.ENCRYPTED_FERNET

        # JSON
        if raw_key.startswith('{') or raw_key.startswith('['):
            try:
                import json
                json.loads(raw_key)
                return KeyFormat.JSON
            except Exception:
                pass

        return KeyFormat.RAW

    def _is_base64(self, s: str) -> bool:
        """检查是否是Base64编码"""
        if not isinstance(s, str):
            return False
        if len(s) < 4:
            return False
        try:
            return base64.urlsafe_b64decode(s) is not None
        except Exception:
            return False

    def _is_hex(self, s: str) -> bool:
        """检查是否是十六进制"""
        return bool(re.match(r'^[A-Fa-f0-9]+$', s))

    def _is_encrypted(self, raw_key: str) -> bool:
        """检查密钥是否加密"""
        return raw_key.startswith('gAAAAA') or raw_key.startswith('ENC[')

    def _decrypt_key(self, encrypted_key: str) -> str:
        """解密密钥"""
        try:
            if encrypted_key.startswith('gAAAAA'):
                # Fernet加密格式
                decrypted = self.cipher.decrypt(encrypted_key.encode())
                return decrypted.decode()
            elif encrypted_key.startswith('ENC['):
                # 自定义ENC格式
                import json
                enc_data = json.loads(encrypted_key[4:])
                decrypted = self.cipher.decrypt(base64.b64decode(enc_data['data']))
                return decrypted.decode()
            else:
                return encrypted_key
        except Exception as e:
            logger.error(f"密钥解密失败: {e}")
            raise ValueError(f"无法解密密钥: {e}")

    def _detect_key_type(self, provider: str, key_value: str) -> KeyType:
        """检测密钥类型"""
        provider_lower = provider.lower()

        # 先尝试已知提供商模式匹配
        for ptn_provider, pattern_info in self.KEY_PATTERNS.items():
            if provider_lower == ptn_provider or ptn_provider in provider_lower:
                pattern = pattern_info['pattern']
                if re.match(pattern, key_value):
                    return pattern_info['type']

        # 通用模式检测
        # JWT
        if re.match(r'^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$', key_value):
            return KeyType.JWT_TOKEN

        # Bearer Token（通用）
        if len(key_value) > 20 and not self._is_hex(key_value):
            return KeyType.BEARER_TOKEN

        # API Key（通用）
        if len(key_value) > 10:
            return KeyType.API_KEY

        return KeyType.UNKNOWN

    def _validate_format(self, provider: str, key_value: str, key_type: KeyType) -> ValidationResult:
        """
        验证密钥格式

        Returns:
            ValidationResult: 验证结果
        """
        errors = []
        warnings = []
        metadata = {}

        # 非空检查
        if not key_value:
            errors.append("密钥值为空")
            return ValidationResult(is_valid=False, errors=errors)

        # 长度检查
        if len(key_value) < 5:
            warnings.append(f"密钥长度过短: {len(key_value)}")
        elif len(key_value) > 500:
            warnings.append(f"密钥长度异常: {len(key_value)}")

        # 类型特定验证
        for ptn_provider, pattern_info in self.KEY_PATTERNS.items():
            if provider.lower() == ptn_provider:
                pattern = pattern_info['pattern']
                if not re.match(pattern, key_value):
                    # 记录警告但不作为错误
                    warnings.append(f"密钥格式与 {ptn_provider} 标准格式不完全匹配")

        # 检查是否是明显的测试密钥
        if self._is_test_key(key_value):
            warnings.append("检测到可能是测试密钥")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata=metadata
        )

    def _is_test_key(self, key_value: str) -> bool:
        """检查是否是测试密钥"""
        test_patterns = [
            'test', 'xxx', 'dummy', 'fake', 'mock',
            'sk-test', 'sk-xx', 'sk-dummy'
        ]
        key_lower = key_value.lower()
        return any(pattern in key_lower for pattern in test_patterns)

    def _should_online_validate(self, key_type: KeyType) -> bool:
        """判断是否应该在线验证"""
        # API密钥和OAuth令牌可以在线验证
        return key_type in [
            KeyType.API_KEY,
            KeyType.OAUTH_TOKEN,
            KeyType.JWT_TOKEN,
        ]

    def _validate_key_online(self, provider: str, key_value: str) -> bool:
        """
        在线验证密钥有效性（实际实现中可能需要调用provider的API）

        注意：这是一个简化的实现，实际应该根据不同provider调用对应的验证API
        """
        # 检查缓存
        cache_key = f"{provider}:{self._get_key_fingerprint(key_value)}"
        with self._lock:
            if cache_key in self._validation_cache:
                cached = self._validation_cache[cache_key]
                if (datetime.now() - cached.metadata.get('cached_at', datetime.min)).seconds < 3600:
                    return cached.is_valid

        # 简化的验证逻辑
        # 实际实现中应该调用各provider的验证API
        try:
            if 'openai' in provider.lower():
                is_valid = self._validate_openai_key(key_value)
            elif 'anthropic' in provider.lower():
                is_valid = self._validate_anthropic_key(key_value)
            elif 'aws' in provider.lower():
                is_valid = self._validate_aws_key(key_value)
            else:
                # 默认认为有效
                is_valid = len(key_value) > 10
        except Exception as e:
            logger.warning(f"在线验证 {provider} 失败: {e}")
            is_valid = True  # 验证失败时默认有效

        # 缓存结果
        with self._lock:
            result = ValidationResult(
                is_valid=is_valid,
                metadata={'cached_at': datetime.now()}
            )
            self._validation_cache[cache_key] = result

        return is_valid

    def _validate_openai_key(self, key: str) -> bool:
        """验证OpenAI API Key"""
        # 实际应该调用 OpenAI API
        # 这里简化处理
        return key.startswith('sk-') and len(key) > 40

    def _validate_anthropic_key(self, key: str) -> bool:
        """验证Anthropic API Key"""
        return key.startswith('sk-ant-') and len(key) > 40

    def _validate_aws_key(self, key: str) -> bool:
        """验证AWS密钥"""
        return key.startswith('AKIA') and len(key) == 20

    def _estimate_expiry(self, provider: str, key_type: KeyType) -> Optional[datetime]:
        """估算密钥过期时间"""
        from datetime import timedelta

        # 从已知过期时间表查找
        for known_type, days in self.KNOWN_EXPIRY.items():
            if known_type in provider.lower() or key_type.value == known_type:
                return datetime.now() + timedelta(days=days)

        # AWS Access Key 1年过期
        if key_type == KeyType.AWS_ACCESS_KEY:
            return datetime.now() + timedelta(days=365)

        # JWT 通常1天过期
        if key_type == KeyType.JWT_TOKEN:
            return datetime.now() + timedelta(days=1)

        # 默认永不过期
        return None

    def _check_rotation_needed(self, provider: str, key_value: str) -> bool:
        """检查是否需要轮转"""
        # 检测已知的不安全密钥模式
        insecure_patterns = [
            r'^test',
            r'^sk-[a-z]+$',  # sk-test
            r'^sk-xx+',
        ]

        for pattern in insecure_patterns:
            if re.match(pattern, key_value, re.IGNORECASE):
                return True

        return False

    def _get_key_fingerprint(self, key: str) -> str:
        """获取密钥指纹（用于缓存）"""
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _get_key_source(self, provider: str) -> str:
        """获取密钥来源"""
        # 可以根据provider名称返回来源信息
        sources = {
            'openai': 'openai_platform',
            'anthropic': 'anthropic_platform',
            'aws': 'aws_iam',
            'azure': 'azure_ad',
            'google': 'gcp_iam',
        }
        return sources.get(provider.lower(), 'unknown')

    def encrypt_key(self, key_value: str) -> str:
        """
        加密密钥（用于安全存储）

        Returns:
            Fernet加密格式的密钥字符串
        """
        return self.cipher.encrypt(key_value.encode()).decode()

    def decrypt_key(self, encrypted_key: str) -> str:
        """
        解密密钥

        Args:
            encrypted_key: Fernet加密格式的密钥

        Returns:
            解密后的原始密钥
        """
        return self.cipher.decrypt(encrypted_key.encode()).decode()

    def generate_key_id(self, key_value: str) -> str:
        """生成密钥唯一标识符"""
        return hashlib.sha256(f"{key_value}{datetime.now()}".encode()).hexdigest()[:16]

    def get_validation_cache(self) -> Dict[str, ValidationResult]:
        """获取验证缓存"""
        return self._validation_cache.copy()

    def clear_validation_cache(self):
        """清空验证缓存"""
        with self._lock:
            self._validation_cache.clear()