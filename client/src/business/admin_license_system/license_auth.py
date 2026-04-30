"""
序列号生成权限控制
License Generation Authorization Control

核心理念：
只有管理员才能生成序列号
作者自动拥有所有权限
"""

import hashlib
import hmac
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum

from .admin_auth import AdminAuth, AdminUser, AdminPermission, AdminRole, get_admin_auth
from .admin_manager import AdminManager, get_admin_manager


class LicenseGenerationError(Exception):
    """序列号生成错误"""
    pass


class LicenseAuth:
    """
    序列号授权控制系统

    功能：
    1. 验证用户是否有权限生成序列号
    2. 记录序列号生成操作
    3. 审计日志
    """

    def __init__(self):
        self._admin_auth = get_admin_auth()
        self._admin_manager = get_admin_manager()

    def can_generate_license(self, admin_id: str = None) -> Tuple[bool, str]:
        """
        检查是否有权限生成序列号

        Args:
            admin_id: 管理员ID（如果为None，使用当前登录用户）

        Returns:
            Tuple[bool, str]: (是否有权限, 原因)
        """
        # 获取目标用户
        if admin_id:
            user = self._admin_auth.get_admin(admin_id)
        else:
            user = self._admin_auth.current_user

        if not user:
            return False, "用户未登录"

        if not user.is_active:
            return False, "账号已被禁用"

        # 检查权限
        if user.can_generate_license():
            return True, "允许生成序列号"

        # 检查是否为作者
        if user.is_author:
            return True, "作者权限"

        return False, "没有生成序列号的权限"

    def require_license_permission(self):
        """
        装饰器：要求有序列号生成权限

        Usage:
            @license_auth.require_license_permission()
            def generate_license():
                pass
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                can_generate, reason = self.can_generate_license()
                if not can_generate:
                    raise LicenseGenerationError(reason)
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def generate_license_with_auth(
        self,
        version: str,
        expires_days: int,
        features: List[str] = None,
        max_users: int = 1,
        admin_id: str = None
    ) -> Tuple[bool, str, Any]:
        """
        带权限验证的序列号生成

        Args:
            version: 版本
            expires_days: 有效期天数
            features: 功能列表
            max_users: 最大用户数
            admin_id: 管理员ID（可选）

        Returns:
            Tuple[bool, str, LicenseKey]: (是否成功, 消息, 生成的序列号)
        """
        # 验证权限
        can_generate, reason = self.can_generate_license(admin_id)
        if not can_generate:
            return False, reason, None

        # 获取管理员信息
        if admin_id:
            user = self._admin_auth.get_admin(admin_id)
        else:
            user = self._admin_auth.current_user

        # 导入激活码生成器
        try:
            from business.activation_license import LicenseGenerator, LicenseVersion, get_license_generator

            version_map = {
                'PER': LicenseVersion.PERSONAL,
                'PRO': LicenseVersion.PROFESSIONAL,
                'ENT': LicenseVersion.ENTERPRISE,
            }

            version_enum = version_map.get(version.upper(), LicenseVersion.PROFESSIONAL)

            generator = get_license_generator()

            # 记录生成日志
            self._admin_manager._log_action(
                admin_id=user.id,
                admin_username=user.username,
                action="GENERATE_LICENSE",
                details=f"生成了 {version} 版本序列号，有效期 {expires_days} 天"
            )

            # 生成序列号
            key = generator.generate(
                version=version_enum,
                expires_days=expires_days,
                features=features,
                max_users=max_users,
                metadata={
                    'generated_by': user.id,
                    'generated_username': user.username,
                    'generated_at': datetime.now().isoformat(),
                }
            )

            return True, "序列号生成成功", key

        except Exception as e:
            return False, f"生成失败: {e}", None

    def generate_batch_with_auth(
        self,
        version: str,
        count: int,
        expires_days: int,
        features: List[str] = None,
        max_users: int = 1,
        batch_name: str = "",
        admin_id: str = None
    ) -> Tuple[bool, str, Any]:
        """
        带权限验证的批量序列号生成

        Args:
            version: 版本
            count: 数量
            expires_days: 有效期天数
            features: 功能列表
            max_users: 最大用户数
            batch_name: 批次名称
            admin_id: 管理员ID

        Returns:
            Tuple[bool, str, GeneratedBatch]: (是否成功, 消息, 批次)
        """
        # 验证权限
        can_generate, reason = self.can_generate_license(admin_id)
        if not can_generate:
            return False, reason, None

        # 数量限制
        if count > 1000:
            return False, "单次批量生成不能超过1000个", None

        # 获取管理员信息
        if admin_id:
            user = self._admin_auth.get_admin(admin_id)
        else:
            user = self._admin_auth.current_user

        try:
            from business.activation_license import LicenseGenerator, LicenseVersion, get_license_generator

            version_map = {
                'PER': LicenseVersion.PERSONAL,
                'PRO': LicenseVersion.PROFESSIONAL,
                'ENT': LicenseVersion.ENTERPRISE,
            }

            version_enum = version_map.get(version.upper(), LicenseVersion.PROFESSIONAL)

            generator = get_license_generator()

            # 记录生成日志
            self._admin_manager._log_action(
                admin_id=user.id,
                admin_username=user.username,
                action="GENERATE_LICENSE_BATCH",
                details=f"批量生成了 {count} 个 {version} 版本序列号，有效期 {expires_days} 天"
            )

            # 批量生成
            batch = generator.generate_batch(
                version=version_enum,
                count=count,
                expires_days=expires_days,
                features=features,
                max_users=max_users,
                batch_name=batch_name,
                created_by=user.username
            )

            return True, f"成功生成 {count} 个序列号", batch

        except Exception as e:
            return False, f"批量生成失败: {e}", None

    def get_generation_history(
        self,
        admin_id: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取序列号生成历史

        Args:
            admin_id: 管理员ID
            limit: 返回数量

        Returns:
            List[Dict]: 生成历史
        """
        logs = self._admin_manager.get_audit_logs(
            admin_id=admin_id,
            action="GENERATE_LICENSE",
            limit=limit
        )

        return [
            {
                'admin_id': log.admin_id,
                'admin_username': log.admin_username,
                'details': log.details,
                'created_at': log.created_at,
            }
            for log in logs
        ]

    def verify_admin_signature(self, admin_id: str, signature: str) -> bool:
        """
        验证管理员签名

        用于验证管理员身份，确保序列号是由合法管理员生成的

        Args:
            admin_id: 管理员ID
            signature: 签名

        Returns:
            bool: 是否验证通过
        """
        user = self._admin_auth.get_admin(admin_id)
        if not user:
            return False

        # 生成签名
        data = f"{user.id}:{user.username}:{user.role}"
        expected_sig = hashlib.sha256(data.encode()).hexdigest()[:16].upper()

        return hmac.compare_digest(signature.upper(), expected_sig)


# 单例
_license_auth: Optional[LicenseAuth] = None


def get_license_auth() -> LicenseAuth:
    """获取序列号授权控制单例"""
    global _license_auth
    if _license_auth is None:
        _license_auth = LicenseAuth()
    return _license_auth