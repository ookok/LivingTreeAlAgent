"""
Payment Gateway API - 统一支付网关 API
======================================

提供支付订单创建、支付、回调等接口
"""

from typing import Optional, Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import sys
_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(_root))

from server.relay_server.services.user_auth_service import require_auth
from server.relay_server.services.payment_gateway import (
    get_payment_gateway,
    PaymentPlatform,
    PayStatus,
    UnifiedPaymentGateway,
)


router = APIRouter(prefix="/api/payment", tags=["支付网关"])


# ============ 请求/响应模型 ============

class CreatePaymentOrderRequest(BaseModel):
    """创建支付订单请求"""
    node_id: str = Field(..., description="节点ID")
    amount: float = Field(..., gt=0, description="支付金额（元）")
    subject: str = Field(..., min_length=1, max_length=256, description="订单标题")
    description: Optional[str] = Field(default=None, max_length=1000, description="订单描述")
    platform: str = Field(default="wechat", description="支付平台：wechat/alipay")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="自定义数据")
    expire_minutes: int = Field(default=30, ge=5, le=120, description="订单有效期（分钟）")


class PaymentCallbackRequest(BaseModel):
    """支付回调请求"""
    order_id: str
    platform: str
    status: str
    trade_no: Optional[str] = None
    paid_at: Optional[int] = None
    amount: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class WechatCallbackRequest(BaseModel):
    """微信支付回调"""
    return_code: Optional[str] = None
    return_msg: Optional[str] = None
    result_code: Optional[str] = None
    mch_id: Optional[str] = None
    appid: Optional[str] = None
    sign: Optional[str] = None
    out_trade_no: Optional[str] = None
    transaction_id: Optional[str] = None
    trade_type: Optional[str] = None
    trade_state: Optional[str] = None
    total_fee: Optional[int] = None
    cash_fee: Optional[int] = None
    time_end: Optional[str] = None


class AlipayCallbackRequest(BaseModel):
    """支付宝回调"""
    out_trade_no: Optional[str] = None
    trade_no: Optional[str] = None
    trade_status: Optional[str] = None
    total_amount: Optional[str] = None
    receipt_amount: Optional[str] = None
    buyer_pay_amount: Optional[str] = None
    gmt_payment: Optional[str] = None


# ============ 支付订单 API ============

@router.post("/orders")
@require_auth
async def create_order(request: Request, body: CreatePaymentOrderRequest):
    """
    创建支付订单
    
    用户在指定节点上创建订单，然后获取支付链接完成支付
    """
    from server.relay_server.services.user_auth_service import get_node_service
    
    node_service = get_node_service()
    node = node_service.storage.get_node_by_id(body.node_id)
    
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    
    if node.user_id != request.state.user_id:
        raise HTTPException(status_code=403, detail="无权限在此节点下单")
    
    # 解析支付平台
    platform_map = {
        "wechat": PaymentPlatform.WECHAT,
        "alipay": PaymentPlatform.ALIPAY,
    }
    platform = platform_map.get(body.platform.lower())
    if not platform:
        raise HTTPException(status_code=400, detail=f"不支持的支付平台: {body.platform}")
    
    # 创建订单
    payment_gateway = get_payment_gateway()
    import uuid
    order_id = f"ord_{uuid.uuid4().hex[:16]}"
    
    order = await payment_gateway.create_order(
        order_id=order_id,
        node_id=body.node_id,
        user_id=request.state.user_id,
        amount=body.amount,
        subject=body.subject,
        platform=platform,
        description=body.description,
        metadata=body.metadata,
        expire_minutes=body.expire_minutes,
    )
    
    # 获取支付链接
    notify_url = f"{request.url.scheme}://{request.url.netloc}/api/payment/callback/{order.order_id}"
    pay_url, error = await payment_gateway.get_pay_url(order, notify_url)
    
    return {
        "success": True,
        "order": order.to_dict(),
        "pay_url": pay_url,
        "pay_url_type": "qrcode" if not pay_url else "link",
    }


@router.get("/orders")
@require_auth
async def list_orders(
    request: Request,
    node_id: Optional[str] = Query(default=None, description="筛选节点"),
    status: Optional[str] = Query(default=None, description="筛选状态"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    获取当前用户的订单列表
    """
    payment_gateway = get_payment_gateway()
    
    all_orders = payment_gateway.get_user_orders(request.state.user_id)
    
    # 筛选
    if node_id:
        all_orders = [o for o in all_orders if o.node_id == node_id]
    if status:
        all_orders = [o for o in all_orders if o.status.value == status]
    
    # 排序
    all_orders.sort(key=lambda x: x.created_at, reverse=True)
    
    # 分页
    total = len(all_orders)
    orders = all_orders[offset:offset + limit]
    
    return {
        "success": True,
        "orders": [o.to_dict() for o in orders],
        "total": total,
        "limit": limit,
        "offset": offset,
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


@router.get("/orders/{order_id}/pay")
@require_auth
async def get_pay_url(request: Request, order_id: str):
    """
    获取支付链接
    """
    payment_gateway = get_payment_gateway()
    order = payment_gateway.get_order(order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    if order.user_id != request.state.user_id:
        raise HTTPException(status_code=403, detail="无权限操作此订单")
    
    if order.status != PayStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"订单状态不允许支付: {order.status.value}")
    
    notify_url = f"{request.url.scheme}://{request.url.netloc}/api/payment/callback/{order.order_id}"
    pay_url, error = await payment_gateway.get_pay_url(order, notify_url)
    
    if error and not pay_url:
        raise HTTPException(status_code=400, detail=error)
    
    return {
        "success": True,
        "pay_url": pay_url,
    }


# ============ 支付回调 API（微信/支付宝回调）============

@router.post("/callback/wechat")
async def wechat_callback(body: Dict[str, Any]):
    """
    微信支付回调
    
    微信支付完成后会回调此接口
    网关会验证签名、更新订单状态、转发通知到对应节点
    """
    payment_gateway = get_payment_gateway()
    
    success, message = await payment_gateway.handle_wechat_callback(body)
    
    if success:
        # 返回微信要求的格式
        return "<xml><return_code><![CDATA[SUCCESS]]></return_code><return_msg><![CDATA[OK]]></return_msg></xml>"
    else:
        return "<xml><return_code><![CDATA[FAIL]]></return_code><return_msg><![CDATA[ERROR]]></return_msg></xml>"


@router.post("/callback/alipay")
async def alipay_callback(body: Dict[str, Any]):
    """
    支付宝回调
    
    支付宝支付完成后会回调此接口
    """
    payment_gateway = get_payment_gateway()
    
    success, message = await payment_gateway.handle_alipay_callback(body)
    
    if success:
        return "success"
    else:
        return "fail"


@router.post("/callback/{order_id}")
async def generic_callback(order_id: str, body: PaymentCallbackRequest):
    """
    通用支付回调（由节点转发）
    
    当节点的中继服务器收到第三方回调后，可以转发到此接口
    """
    payment_gateway = get_payment_gateway()
    
    order = payment_gateway.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    # 更新状态
    status_map = {
        "pending": PayStatus.PENDING,
        "success": PayStatus.SUCCESS,
        "paid": PayStatus.SUCCESS,
        "failed": PayStatus.FAILED,
        "refunded": PayStatus.REFUNDED,
        "closed": PayStatus.CLOSED,
    }
    new_status = status_map.get(body.status.lower())
    if new_status:
        payment_gateway.storage.update_order_status(order_id, new_status, body.trade_no)
    
    # 转发给节点
    from server.relay_server.services.user_auth_service import get_node_service
    node_service = get_node_service()
    node = node_service.storage.get_node_by_id(order.node_id)
    
    if node and node.relay_url:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                callback_url = f"{node.relay_url.rstrip('/')}/api/payment/callback"
                await client.post(callback_url, json=body.model_dump())
        except Exception:
            pass
    
    return {"success": True, "message": "回调已处理"}


# ============ 节点回调 API（节点实现）============

@router.post("/node/callback")
async def node_payment_callback(body: PaymentCallbackRequest):
    """
    节点支付回调接收
    
    节点的中继服务器实现此接口，接收来自网关的支付通知
    用于节点处理支付完成后的业务逻辑（如发放积分、开通服务等）
    """
    # 此接口由节点的中继服务器实现
    # 网关在处理完第三方回调后，会转发到此接口
    
    order_id = body.order_id
    status = body.status
    trade_no = body.trade_no
    
    # TODO: 节点业务逻辑
    # 例如：
    # - 更新本地订单状态
    # - 发放积分到用户账户
    # - 开通付费功能
    # - 发送通知给用户
    
    return {
        "success": True,
        "message": "节点已收到支付通知",
        "order_id": order_id,
    }


# ============ 管理员 API ============

@router.get("/admin/orders")
@require_auth
async def admin_list_orders(
    request: Request,
    node_id: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    管理员：查看所有订单
    """
    # TODO: 权限检查
    # if not is_admin(request.state.user_id):
    #     raise HTTPException(status_code=403, detail="需要管理员权限")
    
    payment_gateway = get_payment_gateway()
    
    # 获取所有订单
    import json
    orders_file = payment_gateway.storage.orders_file
    all_orders = []
    if orders_file.exists():
        data = json.loads(orders_file.read_text(encoding="utf-8"))
        from server.relay_server.services.payment_gateway import PaymentOrder
        all_orders = [PaymentOrder(**o) for o in data.values()]
    
    # 筛选
    if node_id:
        all_orders = [o for o in all_orders if o.node_id == node_id]
    if user_id:
        all_orders = [o for o in all_orders if o.user_id == user_id]
    if status:
        all_orders = [o for o in all_orders if o.status.value == status]
    
    # 排序和分页
    all_orders.sort(key=lambda x: x.created_at, reverse=True)
    total = len(all_orders)
    orders = all_orders[offset:offset + limit]
    
    return {
        "success": True,
        "orders": [o.to_dict() for o in orders],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/admin/stats")
@require_auth
async def admin_stats(request: Request):
    """
    管理员：支付统计
    """
    payment_gateway = get_payment_gateway()
    
    import json
    orders_file = payment_gateway.storage.orders_file
    all_orders = []
    if orders_file.exists():
        data = json.loads(orders_file.read_text(encoding="utf-8"))
        from server.relay_server.services.payment_gateway import PaymentOrder
        all_orders = [PaymentOrder(**o) for o in data.values()]
    
    # 统计
    total_orders = len(all_orders)
    total_amount = sum(o.amount for o in all_orders if o.status == PayStatus.SUCCESS)
    pending_orders = len([o for o in all_orders if o.status == PayStatus.PENDING])
    
    # 按平台统计
    platform_stats = {}
    for o in all_orders:
        p = o.platform.value if hasattr(o.platform, 'value') else str(o.platform)
        if p not in platform_stats:
            platform_stats[p] = {"count": 0, "amount": 0}
        platform_stats[p]["count"] += 1
        if o.status == PayStatus.SUCCESS:
            platform_stats[p]["amount"] += o.amount
    
    return {
        "success": True,
        "stats": {
            "total_orders": total_orders,
            "total_amount": round(total_amount, 2),
            "pending_orders": pending_orders,
            "platform_stats": platform_stats,
        }
    }
