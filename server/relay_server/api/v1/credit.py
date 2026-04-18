"""
Credit API - 积分充值与VIP系统 API
==================================

Endpoints:
- POST   /api/credit/recharge          # 充值
- GET    /api/credit/account            # 获取账户信息
- GET    /api/credit/vip                # 获取VIP信息
- POST   /api/credit/daily-bonus       # 领取每日赠送
- GET    /api/credit/transactions       # 获取交易记录
- POST   /api/credit/consume            # 消费积分
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Header, Request

from server.relay_server.services.user_auth_service import get_auth_service, UserAuthService
from server.relay_server.services.credit_recharge_service import (
    get_credit_service,
    CreditRechargeService,
    VIPLevel,
    TransactionType,
)


router = APIRouter(prefix="/api/credit", tags=["积分充值"])


def get_current_user_id(request: Request) -> str:
    """从请求中获取当前用户ID"""
    if not hasattr(request.state, "user_id"):
        raise HTTPException(status_code=401, detail="未认证")
    return request.state.user_id


@router.post("/recharge")
async def recharge(
    request: Request,
    amount: float = Query(..., gt=0, description="充值金额（元）"),
    order_id: Optional[str] = Query(None, description="关联订单ID")
):
    """
    用户充值

    积分计算规则：
    - 1元 = 10积分
    - 首次充值额外奖励50%
    - VIP升级奖励（升级时一次性发放）
    """
    user_id = get_current_user_id(request)
    credit_service = get_credit_service()

    # 获取充值前的账户信息（用于计算）
    old_account = credit_service.get_account(user_id)
    old_vip = old_account.vip_level if old_account else VIPLevel.NONE

    # 执行充值
    credits_obtained, account, error = credit_service.recharge(
        user_id=user_id,
        amount=amount,
        order_id=order_id
    )

    if error:
        raise HTTPException(status_code=400, detail=error)

    # 计算奖励详情
    bonus_details = []
    base_credits = int(amount * 10)  # 1元=10积分

    if not old_account or not old_account.is_first_recharge_done:
        first_bonus = int(base_credits * 0.5)
        bonus_details.append(f"首次充值奖励: +{first_bonus}积分")

    new_vip = account.vip_level
    if new_vip.level_value > old_vip.level_value:
        upgrade_bonus = {
            VIPLevel.VIP1: 100,
            VIPLevel.VIP2: 300,
            VIPLevel.VIP3: 800,
            VIPLevel.VIP4: 2000,
            VIPLevel.VIP5: 5000,
        }.get(new_vip, 0)
        if upgrade_bonus:
            bonus_details.append(f"升级{new_vip.value}奖励: +{upgrade_bonus}积分")

    return {
        "success": True,
        "data": {
            "amount": amount,                    # 充值金额
            "base_credits": base_credits,       # 基础积分
            "bonus_credits": credits_obtained - base_credits,  # 奖励积分
            "total_credits": credits_obtained, # 总到账积分
            "balance": account.balance,         # 当前余额
            "vip_level": account.vip_level.value,  # VIP等级
            "bonus_details": bonus_details,
        }
    }


@router.get("/account")
async def get_account(request: Request):
    """
    获取积分账户信息
    """
    user_id = get_current_user_id(request)
    credit_service = get_credit_service()

    account = credit_service.get_or_create_account(user_id)

    return {
        "success": True,
        "data": {
            "user_id": account.user_id,
            "balance": account.balance,
            "total_recharged": account.total_recharged,
            "total_earned": account.total_earned,
            "total_consumed": account.total_consumed,
            "vip_level": account.vip_level.value,
            "is_first_recharge_done": account.is_first_recharge_done,
            "created_at": datetime.fromtimestamp(account.created_at).isoformat(),
        }
    }


@router.get("/vip")
async def get_vip_info(request: Request):
    """
    获取VIP详细信息

    返回当前VIP等级、每日赠送额度、下一个等级等信息
    """
    user_id = get_current_user_id(request)
    credit_service = get_credit_service()

    account = credit_service.get_or_create_account(user_id)
    vip_info = credit_service.get_vip_info(account)

    # 格式化时间
    next_claim_in = vip_info.get("next_claim_in_seconds", 0)
    hours = next_claim_in // 3600
    minutes = (next_claim_in % 3600) // 60
    seconds = next_claim_in % 60

    return {
        "success": True,
        "data": {
            "current_level": vip_info["current_level"],
            "current_level_name": vip_info["current_level_name"],
            "daily_bonus": vip_info["daily_bonus"],
            "total_recharged": vip_info["total_recharged"],
            "next_level": vip_info["next_level"],
            "next_level_name": vip_info["next_level_name"],
            "next_level_daily_bonus": vip_info["next_level_daily_bonus"],
            "need_more_to_upgrade": round(vip_info["need_more_to_upgrade"], 2),
            "can_claim_daily_bonus": vip_info["can_claim_daily_bonus"],
            "daily_bonus_available": vip_info["daily_bonus_available"],
            "next_claim_in": f"{hours}小时{minutes}分{seconds}秒" if next_claim_in > 0 else "可立即领取",
        }
    }


@router.post("/daily-bonus")
async def claim_daily_bonus(request: Request):
    """
    领取每日赠送积分

    VIP用户每日可领取对应等级的赠送积分
    - VIP1: 10积分/天
    - VIP2: 30积分/天
    - VIP3: 80积分/天
    - VIP4: 200积分/天
    - VIP5: 500积分/天
    """
    user_id = get_current_user_id(request)
    credit_service = get_credit_service()

    bonus, account, error = credit_service.claim_daily_bonus(user_id)

    if error:
        if "非VIP" in error or "不存在" in error:
            raise HTTPException(status_code=400, detail=error)
        else:
            # 已领取等错误，返回成功但提示
            return {
                "success": True,
                "data": {
                    "bonus": 0,
                    "balance": account.balance if account else 0,
                    "message": error,
                }
            }

    return {
        "success": True,
        "data": {
            "bonus": bonus,
            "balance": account.balance,
            "vip_level": account.vip_level.value,
            "message": f"领取成功！获得 {bonus} 积分"
        }
    }


@router.get("/transactions")
async def get_transactions(
    request: Request,
    limit: int = Query(50, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    tx_type: Optional[str] = Query(None, description="交易类型: recharge/daily_bonus/first_recharge_bonus/vip_upgrade_bonus/consume")
):
    """
    获取交易记录
    """
    user_id = get_current_user_id(request)
    credit_service = get_credit_service()

    transactions = credit_service.get_transactions(
        user_id=user_id,
        limit=limit,
        offset=offset,
        tx_type=tx_type
    )

    # 格式化时间
    tx_list = []
    for tx in transactions:
        tx_list.append({
            "transaction_id": tx.transaction_id,
            "type": tx.type.value,
            "amount": tx.amount,
            "balance_after": tx.balance_after,
            "related_order_id": tx.related_order_id,
            "description": tx.description,
            "created_at": datetime.fromtimestamp(tx.created_at).isoformat(),
        })

    return {
        "success": True,
        "data": {
            "transactions": tx_list,
            "count": len(tx_list),
            "limit": limit,
            "offset": offset,
        }
    }


@router.post("/consume")
async def consume_credits(
    request: Request,
    amount: int = Query(..., gt=0, description="消耗积分数量"),
    description: str = Query("", description="消费描述")
):
    """
    消费积分

    积分不足会返回错误
    """
    user_id = get_current_user_id(request)
    credit_service = get_credit_service()

    success, account, error = credit_service.consume(
        user_id=user_id,
        amount=amount,
        description=description
    )

    if not success:
        raise HTTPException(status_code=400, detail=error)

    return {
        "success": True,
        "data": {
            "consumed": amount,
            "balance": account.balance,
            "description": description or "积分消费",
        }
    }


# ============ VIP等级说明 API ============

@router.get("/vip-levels")
async def get_vip_levels():
    """
    获取VIP等级说明

    返回各VIP等级的充值要求、每日赠送等信息
    """
    levels = [
        {
            "level": "vip1",
            "name": "VIP1",
            "min_recharge": 100,
            "daily_bonus": 10,
            "description": "累计充值满100元",
        },
        {
            "level": "vip2",
            "name": "VIP2",
            "min_recharge": 500,
            "daily_bonus": 30,
            "description": "累计充值满500元",
        },
        {
            "level": "vip3",
            "name": "VIP3",
            "min_recharge": 1000,
            "daily_bonus": 80,
            "description": "累计充值满1000元",
        },
        {
            "level": "vip4",
            "name": "VIP4",
            "min_recharge": 5000,
            "daily_bonus": 200,
            "description": "累计充值满5000元",
        },
        {
            "level": "vip5",
            "name": "VIP5",
            "min_recharge": 10000,
            "daily_bonus": 500,
            "description": "累计充值满10000元",
        },
    ]

    return {
        "success": True,
        "data": {
            "recharge_rate": "1元 = 10积分",
            "first_recharge_bonus": "首充额外奖励50%积分",
            "upgrade_bonus": {
                "vip1": "升级奖励100积分",
                "vip2": "升级奖励300积分",
                "vip3": "升级奖励800积分",
                "vip4": "升级奖励2000积分",
                "vip5": "升级奖励5000积分",
            },
            "levels": levels,
        }
    }
