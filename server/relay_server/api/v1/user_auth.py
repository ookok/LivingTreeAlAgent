"""
User Auth API - 用户认证 API
=============================

提供用户注册、登录、Token刷新、节点管理等接口
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import sys
_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(_root))

from server.relay_server.services.user_auth_service import (
    get_auth_service,
    get_node_service,
    get_payment_gateway,
    require_auth,
    AuthProvider,
    NodeStatus,
    PaymentStatus,
)


router = APIRouter(prefix="/api/auth", tags=["认证"])


# ============ 请求/响应模型 ============

class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=32, pattern=r'^[a-zA-Z0-9_]+$')
    password: str = Field(..., min_length=8, max_length=128)
    email: Optional[str] = Field(default=None)
    node_name: Optional[str] = Field(default=None, description="节点名称")
    relay_url: Optional[str] = Field(default=None, description="节点 Relay URL")


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str
    node_id: Optional[str] = Field(default=None, description="关联的节点ID")


class TokenRefreshRequest(BaseModel):
    """Token刷新请求"""
    refresh_token: str


class OAuthLoginRequest(BaseModel):
    """第三方登录请求"""
    provider: str = Field(..., description="github/google/wechat")
    provider_user_id: str = Field(..., description="第三方用户ID")
    username: Optional[str] = Field(default=None)
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    node_name: Optional[str] = None
    relay_url: Optional[str] = None


class NodeRegisterRequest(BaseModel):
    """节点注册请求"""
    node_name: str = Field(..., min_length=1, max_length=128)
    relay_url: str = Field(..., description="节点 Relay URL")
    public_key: Optional[str] = Field(default=None)
    client_id: Optional[str] = Field(default=None)
    platform: str = "unknown"
    version: str = "2.0.0"
    capabilities: List[str] = []


class HeartbeatRequest(BaseModel):
    """节点心跳"""
    node_id: str
    timestamp: Optional[int] = None


class CreateOrderRequest(BaseModel):
    """创建支付订单"""
    node_id: str
    amount: float = Field(..., gt=0)
    subject: str = Field(..., min_length=1, max_length=256)
    payment_method: Optional[str] = Field(default=None, description="wechat/alipay")
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class PaymentCallbackRequest(BaseModel):
    """支付回调"""
    order_id: str
    payment_method: str
    trade_no: Optional[str] = None
    status: str
    paid_at: Optional[int] = None
    amount: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


# ============ 用户认证 API ============

@router.post("/register")
async def register(request: RegisterRequest):
    """
    用户注册（自动注册节点）
    
    用户注册时自动创建一个关联节点，节点状态为 PENDING（作者用户为 ACTIVE）
    """
    auth_service = get_auth_service()
    
    user, node, error = auth_service.register(
        username=request.username,
        password=request.password,
        email=request.email,
        auto_create_node=True,
        node_name=request.node_name,
        relay_url=request.relay_url,
    )
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    # 生成 Token
    access_token = auth_service.create_access_token(user.user_id, user.username, node.node_id if node else None)
    refresh_token = auth_service.create_refresh_token(user.user_id)
    
    return {
        "success": True,
        "message": "注册成功",
        "user": user.to_dict(),
        "node": node.to_dict() if node else None,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
    }


@router.post("/login")
async def login(request: LoginRequest):
    """
    用户登录
    
    支持用户名密码登录，返回 JWT Token
    """
    auth_service = get_auth_service()
    
    access_token, refresh_token, user, error = auth_service.login(
        username=request.username,
        password=request.password,
        node_id=request.node_id,
    )
    
    if error:
        raise HTTPException(status_code=401, detail=error)
    
    # 获取用户节点列表
    node_service = get_node_service()
    nodes = node_service.get_user_nodes(user.user_id)
    
    return {
        "success": True,
        "message": "登录成功",
        "user": user.to_dict(),
        "nodes": [n.to_dict() for n in nodes],
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
    }


@router.post("/refresh")
async def refresh_token(request: TokenRefreshRequest):
    """
    刷新访问令牌
    """
    auth_service = get_auth_service()
    
    new_access_token, error = auth_service.refresh_access_token(request.refresh_token)
    
    if error:
        raise HTTPException(status_code=401, detail=error)
    
    return {
        "success": True,
        "access_token": new_access_token,
        "token_type": "Bearer",
    }


@router.post("/oauth")
async def oauth_login(request: OAuthLoginRequest):
    """
    第三方认证登录/注册
    
    支持 GitHub、Google、微信等 OAuth 提供者
    """
    auth_service = get_auth_service()
    
    # 解析 provider
    provider_map = {
        "github": AuthProvider.GITHUB,
        "google": AuthProvider.GOOGLE,
        "wechat": AuthProvider.WECHAT,
    }
    provider = provider_map.get(request.provider.lower())
    if not provider:
        raise HTTPException(status_code=400, detail=f"不支持的 OAuth 提供者: {request.provider}")
    
    user, node, error = auth_service.oauth_register_or_login(
        provider=provider,
        provider_user_id=request.provider_user_id,
        username=request.username,
        email=request.email,
        display_name=request.display_name,
        avatar_url=request.avatar_url,
        auto_create_node=True,
        node_name=request.node_name,
        relay_url=request.relay_url,
    )
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    # 生成 Token
    access_token = auth_service.create_access_token(user.user_id, user.username, node.node_id if node else None)
    refresh_token = auth_service.create_refresh_token(user.user_id)
    
    return {
        "success": True,
        "message": "登录成功",
        "user": user.to_dict(),
        "node": node.to_dict() if node else None,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
    }


@router.get("/me")
@require_auth
async def get_current_user(request: Request):
    """
    获取当前用户信息
    """
    auth_service = get_auth_service()
    user = auth_service.storage.get_user_by_id(request.state.user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 获取用户节点
    node_service = get_node_service()
    nodes = node_service.get_user_nodes(user.user_id)
    
    return {
        "success": True,
        "user": user.to_dict(),
        "nodes": [n.to_dict() for n in nodes],
    }


# ============ 节点管理 API ============

@router.post("/nodes")
@require_auth
async def register_node(request: Request, body: NodeRegisterRequest):
    """
    注册新节点
    
    一个用户可以注册多个节点
    """
    node_service = get_node_service()
    
    node = node_service.register_node(
        user_id=request.state.user_id,
        node_name=body.node_name,
        relay_url=body.relay_url,
        public_key=body.public_key,
        client_id=body.client_id,
        platform=body.platform,
        version=body.version,
        capabilities=body.capabilities,
    )
    
    return {
        "success": True,
        "message": "节点注册成功",
        "node": node.to_dict(),
    }


@router.get("/nodes")
@require_auth
async def list_nodes(request: Request):
    """
    获取用户的所有节点
    """
    node_service = get_node_service()
    nodes = node_service.get_user_nodes(request.state.user_id)
    
    return {
        "success": True,
        "nodes": [n.to_dict() for n in nodes],
        "total": len(nodes),
    }


@router.get("/nodes/{node_id}")
@require_auth
async def get_node(request: Request, node_id: str):
    """
    获取节点详情
    """
    node_service = get_node_service()
    node = node_service.storage.get_node_by_id(node_id)
    
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    
    if node.user_id != request.state.user_id:
        raise HTTPException(status_code=403, detail="无权限查看此节点")
    
    return {
        "success": True,
        "node": node.to_dict(),
    }


@router.post("/nodes/{node_id}/activate")
@require_auth
async def activate_node(request: Request, node_id: str):
    """
    激活节点
    """
    node_service = get_node_service()
    success, message = node_service.activate_node(node_id, request.state.user_id)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "success": True,
        "message": message,
    }


@router.post("/nodes/{node_id}/heartbeat")
async def node_heartbeat(node_id: str, body: HeartbeatRequest):
    """
    节点心跳
    
    无需认证（节点ID作为标识）
    """
    node_service = get_node_service()
    success = node_service.heartbeat(node_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="节点不存在")
    
    return {
        "success": True,
        "server_time": int(datetime.utcnow().timestamp()),
    }


@router.delete("/nodes/{node_id}")
@require_auth
async def delete_node(request: Request, node_id: str):
    """
    删除节点
    """
    node_service = get_node_service()
    node = node_service.storage.get_node_by_id(node_id)
    
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    
    if node.user_id != request.state.user_id:
        raise HTTPException(status_code=403, detail="无权限删除此节点")
    
    node_service.storage.delete_node(node_id)
    
    return {
        "success": True,
        "message": "节点已删除",
    }


# ============ 支付网关 API ============

@router.post("/orders")
@require_auth
async def create_order(request: Request, body: CreateOrderRequest):
    """
    创建支付订单
    
    用户在某个节点上创建订单，用于购买积分、服务等
    """
    payment_gateway = get_payment_gateway()
    node_service = get_node_service()
    
    # 验证节点
    node = node_service.storage.get_node_by_id(body.node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    if node.user_id != request.state.user_id:
        raise HTTPException(status_code=403, detail="无权限在此节点下单")
    
    # 创建订单
    order, error = payment_gateway.create_order(
        user_id=request.state.user_id,
        node_id=body.node_id,
        amount=body.amount,
        subject=body.subject,
        payment_method=body.payment_method,
        metadata=body.metadata,
    )
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    # 获取支付链接
    payment_url = None
    if body.payment_method:
        payment_url, pay_error = payment_gateway.get_payment_url(
            order=order,
            payment_method=body.payment_method,
            notify_url=f"/api/auth/orders/{order.order_id}/callback"
        )
    
    return {
        "success": True,
        "order": order.to_dict(),
        "payment_url": payment_url,
    }


@router.get("/orders")
@require_auth
async def list_orders(request: Request):
    """
    获取用户的所有订单
    """
    payment_gateway = get_payment_gateway()
    orders = payment_gateway.get_user_orders(request.state.user_id)
    
    return {
        "success": True,
        "orders": [o.to_dict() for o in orders],
        "total": len(orders),
    }


@router.get("/orders/{order_id}")
@require_auth
async def get_order(request: Request, order_id: str):
    """
    获取订单详情
    """
    payment_gateway = get_payment_gateway()
    order = payment_gateway.get_order(order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    if order.user_id != request.state.user_id:
        raise HTTPException(status_code=403, detail="无权限查看此订单")
    
    return {
        "success": True,
        "order": order.to_dict(),
    }


@router.post("/orders/{order_id}/pay")
@require_auth
async def get_payment_url(request: Request, order_id: str, payment_method: str = Query(..., description="wechat/alipay")):
    """
    获取支付链接
    """
    payment_gateway = get_payment_gateway()
    order = payment_gateway.get_order(order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    if order.user_id != request.state.user_id:
        raise HTTPException(status_code=403, detail="无权限操作此订单")
    
    if order.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=400, detail="订单状态不允许支付")
    
    payment_url, error = payment_gateway.get_payment_url(
        order=order,
        payment_method=payment_method,
        notify_url=f"/api/auth/orders/{order.order_id}/callback"
    )
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    return {
        "success": True,
        "payment_url": payment_url,
    }


@router.post("/orders/{order_id}/callback")
async def payment_callback(order_id: str, body: PaymentCallbackRequest):
    """
    支付回调
    
    微信/支付宝回调此接口
    网关会验证签名并更新订单状态，然后转发给对应的节点
    """
    payment_gateway = get_payment_gateway()
    
    success, message = await payment_gateway.handle_callback(
        payment_method=body.payment_method,
        callback_data=body.model_dump(),
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


# ============ 管理员 API（需管理员权限）============

@router.get("/admin/users")
@require_auth
async def admin_list_users(request: Request):
    """
    管理员：列出所有用户
    """
    # TODO: 检查管理员权限
    auth_service = get_auth_service()
    storage = auth_service.storage
    
    # 获取所有用户
    import json
    users_file = storage.users_file
    if users_file.exists():
        data = json.loads(users_file.read_text(encoding="utf-8"))
        users = [User(**u) for u in data.values()]
    else:
        users = []
    
    from server.relay_server.services.user_auth_service import User
    return {
        "success": True,
        "users": [u.to_dict() for u in users],
        "total": len(users),
    }


@router.get("/admin/nodes")
@require_auth
async def admin_list_nodes(request: Request):
    """
    管理员：列出所有节点
    """
    # TODO: 检查管理员权限
    node_service = get_node_service()
    storage = node_service.storage
    
    import json
    nodes_file = storage.nodes_file
    if nodes_file.exists():
        data = json.loads(nodes_file.read_text(encoding="utf-8"))
        nodes = [Node(**n) for n in data.values()]
    else:
        nodes = []
    
    from server.relay_server.services.user_auth_service import Node
    return {
        "success": True,
        "nodes": [n.to_dict() for n in nodes],
        "total": len(nodes),
    }
