"""
Auth API - 认证 API
=================

提供用户注册、登录、Token 管理等功能
"""

import time
from typing import Optional, Dict, Any

try:
    from fastapi import APIRouter, HTTPException, Request, Depends
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

if FASTAPI_AVAILABLE:
    router = APIRouter(prefix="/auth", tags=["认证"])
    
    # ============ 请求/响应模型 ============
    
    class RegisterRequest(BaseModel):
        """注册请求"""
        username: str = Field(..., min_length=3, max_length=32)
        email: Optional[str] = None
        password: str = Field(..., min_length=8, max_length=128)
        display_name: Optional[str] = None
    
    
    class LoginRequest(BaseModel):
        """登录请求"""
        username: str
        password: str
    
    
    class TokenResponse(BaseModel):
        """Token 响应"""
        success: bool
        access_token: str
        refresh_token: str
        token_type: str = "Bearer"
        expires_in: int
        user: Dict[str, Any]
    
    
    class RefreshTokenRequest(BaseModel):
        """刷新 Token 请求"""
        refresh_token: str
    
    
    # ============ 认证端点 ============
    
    @router.post("/register", response_model=TokenResponse)
    async def register(request: RegisterRequest, req: Request):
        """
        用户注册
        
        - username: 用户名（3-32位字母数字下划线）
        - email: 邮箱（可选）
        - password: 密码（至少8位，包含字母和数字）
        """
        from ...services.auth_service import get_auth_service
        from ...database import get_db_session, init_sqlite_tables
        
        # 初始化数据库表
        init_sqlite_tables()
        
        auth_service = get_auth_service()
        
        # 验证用户名
        if not auth_service.validate_username(request.username):
            raise HTTPException(
                status_code=400,
                detail="用户名格式不正确（3-32位字母数字下划线）"
            )
        
        # 验证邮箱
        if request.email and not auth_service.validate_email(request.email):
            raise HTTPException(
                status_code=400,
                detail="邮箱格式不正确"
            )
        
        # 验证密码
        is_valid, error_msg = auth_service.validate_password(request.password)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )
        
        # 检查用户是否已存在
        with get_db_session() as session:
            from ...database.models import User
            
            existing = session.query(User).filter(
                (User.username == request.username) | 
                (User.email == request.email)
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="用户名或邮箱已存在"
                )
            
            # 创建用户
            user_id = auth_service.generate_user_id()
            password_hash = auth_service.hash_password(request.password)
            
            user = User(
                user_id=user_id,
                username=request.username,
                email=request.email,
                password_hash=password_hash,
                display_name=request.display_name or request.username,
                auth_provider="local",
            )
            
            session.add(user)
            session.commit()
            session.refresh(user)
            
            user_dict = user.to_dict()
        
        # 生成 Token
        access_token = auth_service.create_access_token(user_id, request.username)
        refresh_token = auth_service.create_refresh_token(user_id)
        
        return TokenResponse(
            success=True,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=86400,  # 24 小时
            user=user_dict,
        )
    
    
    @router.post("/login", response_model=TokenResponse)
    async def login(request: LoginRequest, req: Request):
        """
        用户登录
        
        - username: 用户名
        - password: 密码
        """
        from ...services.auth_service import get_auth_service
        from ...database import get_db_session, init_sqlite_tables
        
        # 初始化数据库表
        init_sqlite_tables()
        
        auth_service = get_auth_service()
        
        # 查找用户
        with get_db_session() as session:
            from ...database.models import User
            
            user = session.query(User).filter(
                User.username == request.username
            ).first()
            
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="用户名或密码错误"
                )
            
            # 验证密码
            if not auth_service.verify_password(request.password, user.password_hash or ""):
                raise HTTPException(
                    status_code=401,
                    detail="用户名或密码错误"
                )
            
            # 检查用户状态
            if not user.is_active:
                raise HTTPException(
                    status_code=403,
                    detail="账户已被禁用"
                )
            
            # 更新登录时间
            from datetime import datetime
            user.last_login_at = datetime.utcnow()
            session.commit()
            
            user_dict = user.to_dict()
        
        # 生成 Token
        access_token = auth_service.create_access_token(user.user_id, user.username)
        refresh_token = auth_service.create_refresh_token(user.user_id)
        
        return TokenResponse(
            success=True,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=86400,
            user=user_dict,
        )
    
    
    @router.post("/refresh")
    async def refresh_token(request: RefreshTokenRequest):
        """
        刷新访问令牌
        
        - refresh_token: 刷新令牌
        """
        from ...services.auth_service import get_auth_service
        from ...database import get_db_session
        from ...database.models import User
        
        auth_service = get_auth_service()
        
        # 验证刷新令牌
        payload = auth_service.verify_token(request.refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=401,
                detail="无效的刷新令牌"
            )
        
        user_id = payload.get("sub")
        
        # 获取用户
        with get_db_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=401,
                    detail="用户不存在或已被禁用"
                )
            
            user_dict = user.to_dict()
        
        # 生成新的访问令牌
        access_token = auth_service.create_access_token(user.user_id, user.username)
        
        return {
            "success": True,
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 86400,
            "user": user_dict,
        }
    
    
    @router.get("/me")
    async def get_current_user(request: Request):
        """
        获取当前用户信息
        
        需要 Authorization: Bearer <token> 头
        """
        from ...services.auth_service import get_auth_service
        from ...database import get_db_session
        from ...database.models import User
        
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid authorization header"
            )
        
        token = auth_header[7:]
        auth_service = get_auth_service()
        payload = auth_service.verify_token(token)
        
        if payload is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
        
        user_id = payload.get("sub")
        
        with get_db_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                raise HTTPException(
                    status_code=404,
                    detail="User not found"
                )
            
            return {
                "success": True,
                "user": user.to_dict(),
            }
    
    
    @router.post("/logout")
    async def logout(request: Request):
        """
        用户登出
        
        注意：这只是客户端行为，服务器会拒绝已过期的 token
        """
        return {
            "success": True,
            "message": "Logged out successfully"
        }
