"""
Notification API - 管理员通知与积分同步 API
==========================================

Endpoints:
- POST /api/admin/notification          # 接收管理员通知（HTTP回调）
- POST /api/admin/heartbeat             # 管理员节点心跳
- GET  /api/admin/online                # 获取在线管理员
- POST /api/credit/sync/push           # 推送积分操作到服务器
- GET  /api/credit/sync/pull           # 从服务器拉取积分数据
- POST /api/credit/sync/claim           # 认领积分操作（用于冲突解决）
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Request, Header
from pydantic import BaseModel, Field
import time

from server.relay_server.services.admin_notification_service import (
    get_admin_notification_service,
    get_admin_online_manager,
    get_serial_request_notifier,
    get_credit_consistency_manager,
    NotificationType,
    NotificationPriority,
)
from server.relay_server.services.credit_recharge_service import get_credit_service
from server.relay_server.services.user_auth_service import get_auth_service, get_node_service


router = APIRouter(prefix="/api", tags=["管理员通知"])


# ============ 请求模型 ============

class NotificationCallbackRequest(BaseModel):
    """通知回调请求"""
    notification_id: str
    notification_type: str
    priority: str
    title: str
    content: str
    data: dict = Field(default_factory=dict)
    created_at: int


class AdminHeartbeatRequest(BaseModel):
    """管理员心跳请求"""
    node_id: str = Field(..., description="节点ID")
    relay_url: str = Field("", description="节点的中继URL")


class SyncPushRequest(BaseModel):
    """积分同步推送请求"""
    user_id: str
    operations: List[dict]
    client_version: int = 0


class SyncPullResponse(BaseModel):
    """积分同步拉取响应"""
    success: bool
    data: dict
    message: str = ""


# ============ 管理员通知端点 ============

@router.post("/admin/notification")
async def receive_notification(request: NotificationCallbackRequest):
    """
    接收管理员通知（HTTP回调）

    节点上的管理员客户端应该实现此端点来接收通知
    """
    # TODO: 根据 notification_type 处理不同的通知
    notification_type = request.notification_type
    title = request.title
    content = request.content
    data = request.data

    # 处理序列号申请通知
    if notification_type == NotificationType.SERIAL_REQUEST.value:
        # 可以在这里触发桌面通知、声音提醒等
        pass

    return {"success": True, "received": True}


@router.post("/admin/heartbeat")
async def admin_heartbeat(
    request: Request,
    body: AdminHeartbeatRequest
):
    """
    管理员节点心跳

    管理员节点定期发送心跳以表明在线状态
    """
    # 获取当前用户（需要认证）
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未认证")

    token = auth_header[7:]
    auth_service = get_auth_service()
    payload = auth_service.verify_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="无效的令牌")

    user_id = payload.get("sub")

    # 更新在线状态
    online_manager = get_admin_online_manager()
    online_manager.update_heartbeat(
        node_id=body.node_id,
        admin_id=user_id,
        relay_url=body.relay_url
    )

    return {
        "success": True,
        "node_id": body.node_id,
        "timestamp": int(time.time()),
    }


@router.get("/admin/online")
async def get_online_admins(
    request: Request,
    min_count: int = Query(1, ge=1, description="最少返回数量")
):
    """
    获取在线管理员列表

    用于检查有多少管理员在线
    """
    # 需要认证
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未认证")

    online_manager = get_admin_online_manager()
    online_admins = online_manager.get_online_admins()

    return {
        "success": True,
        "data": {
            "total_online": len(online_admins),
            "admins": [
                {
                    "node_id": admin.node_id,
                    "admin_id": admin.admin_id,
                    "admin_username": admin.admin_username,
                    "last_heartbeat": datetime.fromtimestamp(admin.last_heartbeat).isoformat(),
                }
                for admin in online_admins
            ],
        }
    }


# ============ 积分同步端点 ============

@router.post("/credit/sync/push")
async def sync_push_credits(request: SyncPushRequest):
    """
    客户端推送积分操作到服务器

    用于：
    1. 离线操作同步
    2. 冲突解决
    """
    credit_service = get_credit_service()
    consistency_manager = get_credit_consistency_manager()

    user_id = request.user_id
    operations = request.operations
    client_version = request.client_version

    # 检查版本冲突
    account = credit_service.get_account(user_id)
    server_version = account.vip_level.level_value if account else 0

    results = []
    conflicts = []

    for op in operations:
        op_id = op.get("op_id")
        op_type = op.get("op_type")
        amount = op.get("amount")
        timestamp = op.get("timestamp", 0)
        version = op.get("version", 0)

        # 检查是否是重复操作（幂等性）
        existing_ops = consistency_manager.get_pending_sync()
        if any(existing.get("op_id") == op_id for existing in existing_ops):
            results.append({"op_id": op_id, "status": "already_processed"})
            continue

        # 添加到同步队列
        consistency_manager.add_to_sync_queue({
            "op_id": op_id,
            "op_type": op_type,
            "user_id": user_id,
            "amount": amount,
            "timestamp": timestamp,
            "version": version,
            "source_node": "client",
            "retry_count": 0,
        })

        # 应用操作到服务器
        try:
            if op_type in ("recharge", "local_recharge"):
                # 充值
                credits, _, error = credit_service.recharge(user_id, amount / 10, order_id=op_id)
                if error:
                    results.append({"op_id": op_id, "status": "error", "message": error})
                else:
                    results.append({"op_id": op_id, "status": "applied", "credits": credits})
            elif op_type in ("consume", "local_consume"):
                # 消费
                success, _, error = credit_service.consume(user_id, abs(amount), description=f"Sync: {op_id}")
                if not success:
                    results.append({"op_id": op_id, "status": "error", "message": error})
                else:
                    results.append({"op_id": op_id, "status": "applied"})
            elif op_type == "daily_bonus":
                # 每日赠送
                bonus, _, error = credit_service.claim_daily_bonus(user_id)
                if error and "已领取" in error:
                    results.append({"op_id": op_id, "status": "already_claimed"})
                elif error:
                    results.append({"op_id": op_id, "status": "error", "message": error})
                else:
                    results.append({"op_id": op_id, "status": "applied", "bonus": bonus})
            else:
                results.append({"op_id": op_id, "status": "unknown_type"})
        except Exception as e:
            results.append({"op_id": op_id, "status": "exception", "message": str(e)})

    # 获取更新后的账户信息
    updated_account = credit_service.get_account(user_id)

    return {
        "success": True,
        "data": {
            "results": results,
            "server_version": consistency_manager._version,
            "account": {
                "balance": updated_account.balance if updated_account else 0,
                "version": consistency_manager._version,
                "vip_level": updated_account.vip_level.value if updated_account else "none",
            }
        }
    }


@router.get("/credit/sync/pull")
async def sync_pull_credits(
    user_id: str = Query(..., description="用户ID"),
    client_version: int = Query(0, description="客户端版本号")
):
    """
    客户端从服务器拉取积分数据

    用于：
    1. 首次同步
    2. 版本检查
    3. 获取最新积分余额
    """
    credit_service = get_credit_service()
    consistency_manager = get_credit_consistency_manager()

    # 获取账户信息
    account = credit_service.get_or_create_account(user_id)

    # 获取待处理操作（用于冲突检测）
    pending_ops = consistency_manager.get_pending_sync()

    return {
        "success": True,
        "data": {
            "balance": account.balance,
            "version": consistency_manager._version,
            "total_recharged": account.total_recharged,
            "vip_level": account.vip_level.value,
            "is_first_recharge_done": account.is_first_recharge_done,
            "last_modified_at": account.updated_at,
            "pending_ops_count": len(pending_ops),
        }
    }


# ============ 序列号申请通知集成 ============

@router.post("/enterprise/notify-serial-request")
async def notify_serial_request(
    request: Request,
    enterprise_name: str = Query(..., description="企业名称"),
    enterprise_code: str = Query(..., description="8位码"),
    license_type: str = Query("standard", description="许可证类型"),
    client_ip: Optional[str] = Query(None, description="客户端IP")
):
    """
    通知序列号申请（供内部调用）

    当企业客户端申请序列号时，中继服务器调用此接口通知管理员
    """
    # 获取请求者信息
    requester_info = {
        "ip_address": client_ip or request.client.host,
        "timestamp": int(time.time()),
    }

    # 发送通知
    notifier = get_serial_request_notifier()
    success, message = await notifier.notify_serial_request(
        enterprise_name=enterprise_name,
        enterprise_code=enterprise_code,
        license_type=license_type,
        requester_info=requester_info,
    )

    return {
        "success": success,
        "message": message,
        "notification_sent": success,
    }
