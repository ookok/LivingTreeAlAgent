"""
管理员授权系统
Admin Authorization System

核心理念：
- 内置作者信息，三端发布时配置
- 作者登录自动获得管理员权限
- 最多添加100个管理员
- 只有管理员才能生成序列号

设计原则：
1. 作者是最高管理员，发布时内置
2. 管理员由作者添加，限额100人
3. 序列号生成必须管理员权限
4. 所有操作均有审计日志
"""

from .admin_auth import (
    AdminAuth,
    AdminUser,
    AdminRole,
    AdminPermission,
    AuthResult,
    get_admin_auth,
)
from .admin_manager import (
    AdminManager,
    AdminAddResult,
    AdminRemoveResult,
    AdminAuditLog,
    get_admin_manager,
)
from .license_auth import (
    LicenseAuth,
    LicenseGenerationError,
    get_license_auth,
)
from .author_config import (
    AuthorConfig,
    AuthorConfigManager,
    AuthorInfo as ConfigAuthorInfo,
    PlatformBinding,
    Platform,
    get_author_config_manager,
)

__all__ = [
    # 管理员认证
    'AdminAuth',
    'AdminUser',
    'AdminRole',
    'AdminPermission',
    'AuthResult',
    'get_admin_auth',

    # 管理员管理
    'AdminManager',
    'AdminAddResult',
    'AdminRemoveResult',
    'AdminAuditLog',
    'get_admin_manager',

    # 序列号权限
    'LicenseAuth',
    'LicenseGenerationError',
    'get_license_auth',

    # 作者配置
    'AuthorConfig',
    'AuthorConfigManager',
    'ConfigAuthorInfo',
    'PlatformBinding',
    'Platform',
    'get_author_config_manager',
]