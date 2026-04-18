"""API v1 Package - API v1 版本"""
from .auth import router as auth_router
from .enterprise_license import router as enterprise_license_router
from .user_auth import router as user_auth_router
from .payment import router as payment_router
from .credit import router as credit_router
from .notification import router as notification_router
from .serial_admin import router as serial_admin_router

__all__ = [
    "auth_router",
    "enterprise_license_router",
    "user_auth_router",
    "payment_router",
    "credit_router",
    "notification_router",
    "serial_admin_router",
]
