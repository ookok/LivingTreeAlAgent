"""
Enterprise License API - 企业许可证API
======================================

提供企业序列号注册、验证的REST API接口。

接口列表：
- POST /api/v1/enterprise/code/generate - 客户端请求生成8位码
- POST /api/v1/enterprise/serial/generate - 服务端生成序列号
- POST /api/v1/enterprise/register - 用户注册（激活）
- POST /api/v1/enterprise/verify - 登录时验证
- GET  /api/v1/enterprise/info - 获取许可证信息
- POST /api/v1/enterprise/revoke - 撤销许可证

Author: Hermes Desktop Team
"""

from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


# ============ 请求模型 ============

class GenerateCodeRequest(BaseModel):
    """请求生成8位码"""
    enterprise_name: str = Field(..., min_length=2, description="企业名称")
    client_id: Optional[str] = Field(None, description="客户端ID")


class GenerateSerialRequest(BaseModel):
    """请求生成序列号"""
    enterprise_code: str = Field(..., min_length=8, max_length=8, description="8位码")
    enterprise_name: str = Field(..., min_length=2, description="企业名称")
    license_type: str = Field("standard", description="许可证类型: trial/standard/professional/enterprise")
    expires_days: int = Field(365, ge=1, le=3650, description="有效期天数")


class RegisterRequest(BaseModel):
    """注册请求"""
    serial_number: str = Field(..., description="序列号")
    enterprise_code: str = Field(..., min_length=8, max_length=8, description="8位码")
    enterprise_name: str = Field(..., min_length=2, description="企业名称")
    device_fingerprint: Optional[str] = Field(None, description="设备指纹")
    license_key: Optional[str] = Field(None, description="激活密钥")


class VerifyRequest(BaseModel):
    """验证请求"""
    serial_number: str = Field(..., description="序列号")
    enterprise_code: str = Field(..., min_length=8, max_length=8, description="8位码")
    enterprise_name: str = Field(..., min_length=2, description="企业名称")
    device_fingerprint: Optional[str] = Field(None, description="设备指纹")


class RevokeRequest(BaseModel):
    """撤销请求"""
    serial_number: str = Field(..., description="序列号")
    reason: Optional[str] = Field(None, description="撤销原因")


# ============ 响应模型 ============

class CodeResponse(BaseModel):
    """8位码响应"""
    success: bool
    enterprise_code: str
    code_id: str
    expires_at: str
    message: str = ""


class SerialResponse(BaseModel):
    """序列号响应"""
    success: bool
    serial_number: str
    license_key: str
    license_type: str
    expires_at: str
    message: str = ""


class RegisterResponse(BaseModel):
    """注册响应"""
    success: bool
    enterprise_id: str
    registered_at: str
    message: str = ""


class VerifyResponse(BaseModel):
    """验证响应"""
    success: bool
    verified_at: str
    enterprise_info: Dict[str, Any] = {}
    message: str = ""


class LicenseInfoResponse(BaseModel):
    """许可证信息响应"""
    success: bool
    info: Dict[str, Any] = {}


# ============ 路由 ============

router = APIRouter(prefix="/api/v1/enterprise", tags=["企业许可证"])


def get_client_ip(request: Request) -> str:
    """获取客户端IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.post("/code/generate", response_model=CodeResponse)
async def generate_enterprise_code(request: GenerateCodeRequest, req: Request):
    """
    客户端：请求生成8位码

    客户端调用此接口获取8位码，然后用于序列号生成请求。
    8位码有效期30分钟。

    注意：生成8位码时会通知系统管理员
    """
    from ..services.enterprise_license_service import (
        get_license_service,
        EnterpriseLicenseService
    )

    try:
        service = get_license_service()

        # 生成8位码
        enterprise_code = EnterpriseLicenseService.generate_enterprise_code(
            request.enterprise_name
        )

        # 存储码信息（用于后续验证）
        code_id = service.store.save_code(
            enterprise_code=enterprise_code,
            enterprise_name=request.enterprise_name,
            expires_minutes=30
        )

        # 获取过期时间
        code_info = service.store.get_code(code_id)
        expires_at = code_info["expires_at"]

        # ===== 通知管理员有新的序列号申请 =====
        try:
            from ..services.admin_notification_service import (
                get_serial_request_notifier,
                NotificationType,
                NotificationPriority,
            )

            notifier = get_serial_request_notifier()
            await notifier.notification_service.send_notification(
                notification_type=NotificationType.SERIAL_REQUEST,
                title=f"新的序列号申请 - {request.enterprise_name}",
                content=f"""企业名称: {request.enterprise_name}
8位码: {enterprise_code}
申请类型: 等待选择许可证类型
请求IP: {get_client_ip(req)}
时间: {datetime.now().isoformat()}
""",
                data={
                    "enterprise_name": request.enterprise_name,
                    "enterprise_code": enterprise_code,
                    "code_id": code_id,
                    "license_type": "pending",
                    "requester_info": {
                        "ip_address": get_client_ip(req),
                        "client_id": request.client_id,
                        "timestamp": int(time.time()),
                    },
                },
                priority=NotificationPriority.NORMAL,
                target_admin_count=1,
            )
        except Exception as notify_err:
            # 通知失败不影响主流程
            print(f"通知管理员失败: {notify_err}")

        return CodeResponse(
            success=True,
            enterprise_code=enterprise_code,
            code_id=code_id,
            expires_at=expires_at,
            message="8位码生成成功，请妥善保管。管理员已收到申请通知。"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.post("/serial/generate", response_model=SerialResponse)
async def generate_serial_number(request: GenerateSerialRequest, req: Request):
    """
    服务端：生成序列号
    
    根据8位码和企业名称生成序列号。
    此接口应该在服务端内部调用或管理员调用。
    """
    from ..services.enterprise_license_service import (
        get_license_service,
        LicenseType
    )
    
    try:
        service = get_license_service()
        
        # 验证许可证类型
        valid_types = [lt.value for lt in LicenseType]
        if request.license_type not in valid_types:
            raise ValueError(f"无效的许可证类型: {request.license_type}")
        
        # 生成序列号
        serial_number, license_key = service.generate_serial_number(
            enterprise_code=request.enterprise_code,
            enterprise_name=request.enterprise_name,
            license_type=request.license_type,
            expires_days=request.expires_days
        )
        
        # 获取企业信息以获取过期时间
        enterprise = service.store.get_enterprise_by_serial(serial_number)
        
        return SerialResponse(
            success=True,
            serial_number=serial_number,
            license_key=license_key,
            license_type=request.license_type,
            expires_at=enterprise.expires_at if enterprise else "",
            message="序列号生成成功"
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.post("/register", response_model=RegisterResponse)
async def register_enterprise(request: RegisterRequest, req: Request):
    """
    用户注册（激活许可证）
    
    用户拿到序列号后调用此接口完成注册。
    注册时需要提供序列号、8位码和企业名称进行校验。
    """
    from ..services.enterprise_license_service import get_license_service
    
    try:
        service = get_license_service()
        
        success, message, enterprise = service.register_enterprise(
            serial_number=request.serial_number,
            enterprise_code=request.enterprise_code,
            enterprise_name=request.enterprise_name,
            device_fingerprint=request.device_fingerprint or get_client_ip(req),
            license_key=request.license_key
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return RegisterResponse(
            success=True,
            enterprise_id=enterprise.get("enterprise_id", ""),
            registered_at=enterprise.get("registered_at", ""),
            message=message
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")


@router.post("/verify", response_model=VerifyResponse)
async def verify_license(request: VerifyRequest, req: Request):
    """
    登录时验证许可证
    
    企业模式每次登录都需要调用此接口验证许可证有效性。
    """
    from ..services.enterprise_license_service import get_license_service
    
    try:
        service = get_license_service()
        
        success, message, enterprise = service.verify_on_login(
            serial_number=request.serial_number,
            enterprise_code=request.enterprise_code,
            enterprise_name=request.enterprise_name,
            device_fingerprint=request.device_fingerprint or get_client_ip(req)
        )
        
        if not success:
            return VerifyResponse(
                success=False,
                verified_at=datetime.now().isoformat(),
                message=message
            )
        
        return VerifyResponse(
            success=True,
            verified_at=datetime.now().isoformat(),
            enterprise_info={
                "enterprise_id": enterprise.get("enterprise_id", ""),
                "enterprise_name": enterprise.get("enterprise_name", ""),
                "license_type": enterprise.get("license_type", ""),
                "expires_at": enterprise.get("expires_at", "")
            },
            message=message
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证失败: {str(e)}")


@router.get("/info/{serial_number}", response_model=LicenseInfoResponse)
async def get_license_info(serial_number: str):
    """
    获取许可证信息（不验证）
    
    用于在注册前查看许可证信息。
    """
    from ..services.enterprise_license_service import get_license_service
    
    try:
        service = get_license_service()
        
        success, info = service.get_license_info(serial_number)
        
        if not success:
            raise HTTPException(status_code=404, detail="许可证不存在")
        
        return LicenseInfoResponse(success=True, info=info)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/revoke")
async def revoke_license(request: RevokeRequest):
    """
    撤销许可证
    
    管理员撤销某个许可证。
    """
    from ..services.enterprise_license_service import get_license_service
    
    try:
        service = get_license_service()
        
        success, message = service.revoke_license(
            serial_number=request.serial_number,
            reason=request.reason or ""
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {"success": True, "message": message}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"撤销失败: {str(e)}")


# ============ 客户端辅助接口 ============

class ValidateCodeRequest(BaseModel):
    """验证8位码请求"""
    enterprise_name: str
    enterprise_code: str


class ValidateCodeResponse(BaseModel):
    """验证8位码响应"""
    valid: bool
    message: str = ""


@router.post("/code/validate", response_model=ValidateCodeResponse)
async def validate_enterprise_code(request: ValidateCodeRequest):
    """
    客户端：验证8位码
    
    用户输入8位码后调用此接口验证格式是否正确。
    （不验证是否与服务端匹配）
    """
    from ..services.enterprise_license_service import EnterpriseLicenseService
    
    try:
        valid = EnterpriseLicenseService.verify_enterprise_code(
            enterprise_name=request.enterprise_name,
            code=request.enterprise_code
        )
        
        return ValidateCodeResponse(
            valid=valid,
            message="8位码正确" if valid else "8位码与企称名称不匹配"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证失败: {str(e)}")