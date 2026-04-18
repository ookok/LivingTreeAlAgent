"""
Serial Admin API - 序列号管理后台 API
=====================================

提供序列号申请管理和发送功能

接口列表：
- GET  /api/v1/serial/pending       # 获取待处理申请列表
- GET  /api/v1/serial/request/{id}  # 获取申请详情
- POST /api/v1/serial/generate     # 生成序列号
- POST /api/v1/serial/send         # 发送序列号到客户端
- GET  /api/v1/serial/delivery/{client_id}  # 客户端拉取序列号
- POST /api/v1/serial/delivery/confirm     # 客户端确认收到
- GET  /api/v1/serial/history       # 历史记录
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
import time

from server.relay_server.services.user_auth_service import get_auth_service, get_node_service
from server.relay_server.services.enterprise_license_service import get_license_service, LicenseType
from server.relay_server.services.serial_notification_service import (
    get_serial_notification_service,
    get_serial_delivery_service,
)


router = APIRouter(prefix="/api/v1/serial", tags=["序列号管理"])


# ============ 请求模型 ============

class GenerateSerialRequest(BaseModel):
    """生成序列号请求"""
    request_id: str = Field(..., description="申请记录ID")
    license_type: str = Field("standard", description="许可证类型")
    expires_days: int = Field(365, ge=1, le=3650, description="有效期天数")


class SendSerialRequest(BaseModel):
    """发送序列号请求"""
    request_id: str = Field(..., description="申请记录ID")
    client_id: str = Field(..., description="客户端ID")
    delivery_url: str = Field("", description="客户端回调URL")


class DeliveryConfirmRequest(BaseModel):
    """确认收到序列号"""
    delivery_id: str = Field(..., description="投递ID")


# ============ 响应模型 ============

class PendingRequestResponse(BaseModel):
    """待处理申请响应"""
    success: bool
    requests: List[dict]
    total: int


class SerialDetailResponse(BaseModel):
    """序列号详情响应"""
    success: bool
    request_id: str
    enterprise_name: str
    enterprise_code: str
    license_type: str
    status: str
    serial_number: str = ""
    license_key: str = ""
    requested_at: str
    requested_ip: str


class GenerateResponse(BaseModel):
    """生成序列号响应"""
    success: bool
    serial_number: str
    license_key: str
    expires_at: str
    message: str = ""


class SendResponse(BaseModel):
    """发送响应"""
    success: bool
    delivery_id: str
    message: str = ""


# ============ 辅助函数 ============

def get_client_ip(request: Request) -> str:
    """获取客户端IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


# ============ 管理员接口 ============

@router.get("/pending", response_model=PendingRequestResponse)
async def get_pending_requests(request: Request):
    """
    获取待处理的序列号申请列表

    需要管理员权限
    """
    # 验证管理员权限
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未认证")

    token = auth_header[7:]
    auth_service = get_auth_service()
    payload = auth_service.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效的令牌")

    # 获取待处理申请
    notification_service = get_serial_notification_service()
    pending = notification_service.get_pending_requests()

    # 格式化
    requests_list = []
    for req in pending:
        requests_list.append({
            "request_id": req.request_id,
            "enterprise_name": req.enterprise_name,
            "enterprise_code": req.enterprise_code,
            "license_type": req.license_type,
            "status": req.status,
            "requested_at": datetime.fromtimestamp(req.requested_at).isoformat(),
            "requested_ip": req.requested_ip,
            "notification_sent": req.notification_sent,
            "notification_channels": req.notification_channels,
        })

    return PendingRequestResponse(
        success=True,
        requests=requests_list,
        total=len(requests_list)
    )


@router.get("/request/{request_id}", response_model=SerialDetailResponse)
async def get_request_detail(request_id: str, request: Request):
    """
    获取申请详情

    需要管理员权限
    """
    # 验证管理员权限
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未认证")

    token = auth_header[7:]
    auth_service = get_auth_service()
    payload = auth_service.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效的令牌")

    notification_service = get_serial_notification_service()

    if request_id not in notification_service._serial_requests:
        raise HTTPException(status_code=404, detail="申请不存在")

    req = notification_service._serial_requests[request_id]

    return SerialDetailResponse(
        success=True,
        request_id=req.request_id,
        enterprise_name=req.enterprise_name,
        enterprise_code=req.enterprise_code,
        license_type=req.license_type,
        status=req.status,
        serial_number=req.serial_number,
        requested_at=datetime.fromtimestamp(req.requested_at).isoformat(),
        requested_ip=req.requested_ip,
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate_serial(
    body: GenerateSerialRequest,
    request: Request
):
    """
    为申请生成序列号

    需要管理员权限
    """
    # 验证管理员权限
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未认证")

    token = auth_header[7:]
    auth_service = get_auth_service()
    payload = auth_service.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效的令牌")

    notification_service = get_serial_notification_service()
    license_service = get_license_service()

    # 获取申请
    if body.request_id not in notification_service._serial_requests:
        raise HTTPException(status_code=404, detail="申请不存在")

    req = notification_service._serial_requests[body.request_id]

    # 生成序列号
    try:
        serial_number, license_key = license_service.generate_serial_number(
            enterprise_code=req.enterprise_code,
            enterprise_name=req.enterprise_name,
            license_type=body.license_type,
            expires_days=body.expires_days
        )

        # 获取企业信息以获取过期时间
        enterprise = license_service.store.get_enterprise_by_serial(serial_number)
        expires_at = enterprise.expires_at if enterprise else ""

        # 更新申请状态
        notification_service.update_request_status(
            body.request_id,
            status="approved",
            serial_number=serial_number
        )

        return GenerateResponse(
            success=True,
            serial_number=serial_number,
            license_key=license_key,
            expires_at=expires_at,
            message="序列号生成成功"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.post("/send", response_model=SendResponse)
async def send_serial_to_client(
    body: SendSerialRequest,
    request: Request
):
    """
    发送序列号到客户端

    需要管理员权限
    发送成功后客户端会收到通知
    """
    # 验证管理员权限
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未认证")

    token = auth_header[7:]
    auth_service = get_auth_service()
    payload = auth_service.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效的令牌")

    notification_service = get_serial_notification_service()
    delivery_service = get_serial_delivery_service()

    # 获取申请
    if body.request_id not in notification_service._serial_requests:
        raise HTTPException(status_code=404, detail="申请不存在")

    req = notification_service._serial_requests[body.request_id]

    if not req.serial_number:
        raise HTTPException(status_code=400, detail="请先生成序列号")

    # 加入发送队列
    delivery_id = delivery_service.queue_serial_for_delivery(
        request_id=body.request_id,
        serial_number=req.serial_number,
        license_key="",  # TODO: 需要从申请中获取
        enterprise_name=req.enterprise_name,
        enterprise_code=req.enterprise_code,
        client_id=body.client_id,
        delivery_url=body.delivery_url,
    )

    # 更新状态
    notification_service.update_request_status(body.request_id, status="completed")

    return SendResponse(
        success=True,
        delivery_id=delivery_id,
        message="序列号已加入发送队列"
    )


# ============ 客户端接口 ============

@router.get("/delivery/{client_id}")
async def poll_serial_for_client(
    client_id: str,
    request: Request
):
    """
    客户端轮询拉取序列号

    客户端定期调用此接口检查是否有待接收的序列号
    """
    delivery_service = get_serial_delivery_service()
    pending = delivery_service.get_pending_delivery(client_id)

    if not pending:
        return {
            "success": True,
            "has_pending": False,
            "data": None
        }

    # 返回最新的一个
    latest = pending[-1]

    return {
        "success": True,
        "has_pending": True,
        "data": {
            "delivery_id": latest["delivery_id"],
            "serial_number": latest["serial_number"],
            "license_key": latest["license_key"],
            "enterprise_name": latest["enterprise_name"],
            "enterprise_code": latest["enterprise_code"],
            "created_at": datetime.fromtimestamp(latest["created_at"]).isoformat(),
        }
    }


@router.post("/delivery/confirm")
async def confirm_serial_received(
    body: DeliveryConfirmRequest,
    request: Request
):
    """
    客户端确认收到序列号

    确认后序列号从待发送队列中移除
    """
    delivery_service = get_serial_delivery_service()

    success = delivery_service.mark_as_delivered(body.delivery_id)

    if not success:
        raise HTTPException(status_code=404, detail="投递不存在")

    return {
        "success": True,
        "message": "确认成功"
    }


# ============ 历史记录 ============

@router.get("/history")
async def get_serial_history(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    获取序列号历史记录

    需要管理员权限
    """
    # 验证管理员权限
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未认证")

    token = auth_header[7:]
    auth_service = get_auth_service()
    payload = auth_service.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效的令牌")

    notification_service = get_serial_notification_service()

    # 获取所有申请记录
    all_requests = list(notification_service._serial_requests.values())
    all_requests.sort(key=lambda x: x.requested_at, reverse=True)

    # 分页
    total = len(all_requests)
    paginated = all_requests[offset:offset + limit]

    return {
        "success": True,
        "requests": [
            {
                "request_id": req.request_id,
                "enterprise_name": req.enterprise_name,
                "enterprise_code": req.enterprise_code,
                "license_type": req.license_type,
                "status": req.status,
                "serial_number": req.serial_number,
                "requested_at": datetime.fromtimestamp(req.requested_at).isoformat(),
                "notification_sent": req.notification_sent,
            }
            for req in paginated
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
