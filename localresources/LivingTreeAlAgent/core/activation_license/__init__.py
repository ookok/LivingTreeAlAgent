"""
智能授权与实名认证系统
Activation License System

核心理念：
授权码机制 = 付款凭证 = 使用权限

核心组件：
1. LicenseGenerator - 激活码生成器
2. LicenseValidator - 激活码验证器
3. RealNameVerifier - 实名认证器

版本类型：
- PERSONAL (PER) - 个人版：免费，不需要激活
- PROFESSIONAL (PRO) - 专业版：需要激活码
- ENTERPRISE (ENT) - 企业版：需要激活码 + 实名认证

用户限制：
- 个人版：无限制
- 专业版：单设备
- 企业版：最多5个实名用户

使用流程：
1. 用户选择版本 → 购买获得激活码
2. 输入激活码 → 系统验证格式和校验位
3. 企业版额外验证实名（手机号/身份证/人脸）
4. 激活成功 → 解锁对应功能

导出组件：
- LicenseGenerator: 激活码生成
- LicenseValidator: 激活码验证和激活
- RealNameVerifier: 实名认证
- ActivationLicensePanel: UI面板（需要单独导入）
"""

from .crypto_utils import (
    CryptoUtils,
    EncryptedData,
    get_crypto_utils,
)
from .license_generator import (
    LicenseGenerator,
    LicenseGenerator,
    LicenseKey,
    GeneratedBatch,
    LicenseVersion,
    LicenseStatus,
    get_license_generator,
)
from .license_validator import (
    LicenseValidator,
    ValidationResult,
    ValidationResponse,
    ActivationRecord,
    get_license_validator,
)
from .real_name_verifier import (
    RealNameVerifier,
    VerificationType,
    VerificationStatus,
    RealNameUser,
    VerificationRequest,
    get_real_name_verifier,
)


# 版本配置
LICENSE_VERSIONS = {
    'PER': {
        'name': '个人版',
        'requires_activation': False,
        'max_users': 1,
        'features': ['basic_chat', 'basic_writing'],
    },
    'PRO': {
        'name': '专业版',
        'requires_activation': True,
        'max_users': 1,
        'features': ['basic_chat', 'basic_writing', 'advanced_ai', 'api_access'],
    },
    'ENT': {
        'name': '企业版',
        'requires_activation': True,
        'requires_real_name': True,
        'max_users': 5,
        'features': ['basic_chat', 'basic_writing', 'advanced_ai', 'api_access', 'team_management', 'priority_support'],
    },
}


def get_version_config(version_code: str) -> dict:
    """获取版本配置"""
    return LICENSE_VERSIONS.get(version_code.upper(), {})


def is_version_requires_activation(version_code: str) -> bool:
    """检查版本是否需要激活"""
    config = get_version_config(version_code)
    return config.get('requires_activation', False)


def is_version_requires_real_name(version_code: str) -> bool:
    """检查版本是否需要实名"""
    config = get_version_config(version_code)
    return config.get('requires_real_name', False)


def can_use_version(version_code: str, is_activated: bool, is_real_name_verified: bool) -> Tuple[bool, str]:
    """
    检查是否可以使用指定版本
    
    Returns:
        Tuple[bool, str]: (是否可以, 原因)
    """
    config = get_version_config(version_code)
    
    if not config:
        return False, "未知的版本"
    
    if config.get('requires_activation') and not is_activated:
        return False, f"{config['name']}需要激活才能使用"
    
    if config.get('requires_real_name') and not is_real_name_verified:
        return False, f"{config['name']}需要实名认证才能使用"
    
    return True, "可以使用"


# 便捷函数
def generate_license_key(
    version: str = 'PRO',
    expires_days: int = 365,
    features: list = None,
    max_users: int = 1
) -> str:
    """快速生成激活码"""
    version_enum = LicenseVersion[version_code_to_enum(version)]
    gen = get_license_generator()
    key = gen.generate(
        version=version_enum,
        expires_days=expires_days,
        features=features,
        max_users=max_users
    )
    return key.key_string


def license_code_to_enum(version_code: str) -> str:
    """转换版本代码为枚举名称"""
    mapping = {
        'PER': 'PERSONAL',
        'PRO': 'PROFESSIONAL', 
        'ENT': 'ENTERPRISE',
    }
    return mapping.get(version_code.upper(), 'PERSONAL')


def validate_license_key(license_key: str) -> ValidationResponse:
    """快速验证激活码"""
    validator = get_license_validator()
    return validator.check_status(license_key)


def activate_license(
    license_key: str,
    device_id: str,
    user_id: str,
    real_name: str = None,
    id_number: str = None,
    phone: str = None
) -> ValidationResponse:
    """快速激活"""
    validator = get_license_validator()
    return validator.activate(
        license_key=license_key,
        device_id=device_id,
        user_id=user_id,
        real_name=real_name,
        id_number=id_number,
        phone=phone
    )


# 类型提示
from typing import Tuple


__all__ = [
    # 加密工具
    'CryptoUtils',
    'EncryptedData', 
    'get_crypto_utils',
    
    # 激活码生成
    'LicenseGenerator',
    'LicenseKey',
    'GeneratedBatch',
    'LicenseVersion',
    'LicenseStatus',
    'get_license_generator',
    
    # 激活码验证
    'LicenseValidator',
    'ValidationResult',
    'ValidationResponse',
    'ActivationRecord',
    'get_license_validator',
    
    # 实名认证
    'RealNameVerifier',
    'VerificationType',
    'VerificationStatus',
    'RealNameUser',
    'VerificationRequest',
    'get_real_name_verifier',
    
    # 便捷函数
    'get_version_config',
    'is_version_requires_activation',
    'is_version_requires_real_name',
    'can_use_version',
    'generate_license_key',
    'validate_license_key',
    'activate_license',
    'LICENSE_VERSIONS',
]