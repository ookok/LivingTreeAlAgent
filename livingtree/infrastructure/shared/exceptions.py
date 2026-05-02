"""
统一异常体系 (Unified Exception System)

提供统一的异常类型和错误处理机制。
"""

from typing import Dict, Any, Optional


class LTAException(Exception):
    """
    LivingTree AI 基础异常类
    
    所有自定义异常都应继承此类。
    """
    
    code: str = "LTA_ERROR"
    message: str = "系统错误"
    http_status: int = 500
    
    def __init__(self, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message or self.message)
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        return {
            "code": self.code,
            "message": str(self),
            "details": self.details
        }


class ConfigError(LTAException):
    """配置错误"""
    code = "CONFIG_ERROR"
    message = "配置错误"
    http_status = 400


class ValidationError(LTAException):
    """验证错误"""
    code = "VALIDATION_ERROR"
    message = "验证失败"
    http_status = 400


class ServiceNotFoundError(LTAException):
    """服务未找到"""
    code = "SERVICE_NOT_FOUND"
    message = "服务未找到"
    http_status = 404


class CircularDependencyError(LTAException):
    """循环依赖错误"""
    code = "CIRCULAR_DEPENDENCY"
    message = "检测到循环依赖"
    http_status = 500


class DocumentValidationError(LTAException):
    """文档验证错误"""
    code = "DOCUMENT_VALIDATION_ERROR"
    message = "文档验证失败"
    http_status = 400


class TermConflictError(LTAException):
    """术语冲突错误"""
    code = "TERM_CONFLICT"
    message = "术语冲突"
    http_status = 409


class TrainingError(LTAException):
    """训练错误"""
    code = "TRAINING_ERROR"
    message = "训练失败"
    http_status = 500


class RetrievalError(LTAException):
    """检索错误"""
    code = "RETRIEVAL_ERROR"
    message = "检索失败"
    http_status = 500


class ModelNotFoundError(LTAException):
    """模型未找到"""
    code = "MODEL_NOT_FOUND"
    message = "模型未找到"
    http_status = 404


class PermissionError(LTAException):
    """权限错误"""
    code = "PERMISSION_DENIED"
    message = "权限不足"
    http_status = 403


class ResourceNotFoundError(LTAException):
    """资源未找到"""
    code = "RESOURCE_NOT_FOUND"
    message = "资源未找到"
    http_status = 404


class ExternalServiceError(LTAException):
    """外部服务错误"""
    code = "EXTERNAL_SERVICE_ERROR"
    message = "外部服务调用失败"
    http_status = 503


class RateLimitError(LTAException):
    """限流错误"""
    code = "RATE_LIMIT_EXCEEDED"
    message = "请求过于频繁，请稍后重试"
    http_status = 429


class InvalidArgumentError(LTAException):
    """参数错误"""
    code = "INVALID_ARGUMENT"
    message = "参数无效"
    http_status = 400


# 错误码映射
ERROR_CODES = {
    "LTA_ERROR": 500,
    "CONFIG_ERROR": 400,
    "VALIDATION_ERROR": 400,
    "SERVICE_NOT_FOUND": 404,
    "CIRCULAR_DEPENDENCY": 500,
    "DOCUMENT_VALIDATION_ERROR": 400,
    "TERM_CONFLICT": 409,
    "TRAINING_ERROR": 500,
    "RETRIEVAL_ERROR": 500,
    "MODEL_NOT_FOUND": 404,
    "PERMISSION_DENIED": 403,
    "RESOURCE_NOT_FOUND": 404,
    "EXTERNAL_SERVICE_ERROR": 503,
    "RATE_LIMIT_EXCEEDED": 429,
    "INVALID_ARGUMENT": 400
}


def get_http_status(code: str) -> int:
    """根据错误码获取HTTP状态码"""
    return ERROR_CODES.get(code, 500)


def handle_exception(e: Exception) -> Dict[str, Any]:
    """
    统一异常处理
    
    Args:
        e: 异常对象
        
    Returns:
        错误响应字典
    """
    if isinstance(e, LTAException):
        return e.to_dict()
    
    # 处理其他异常
    return {
        "code": "UNKNOWN_ERROR",
        "message": str(e),
        "details": {}
    }


__all__ = [
    "LTAException",
    "ConfigError",
    "ValidationError",
    "ServiceNotFoundError",
    "CircularDependencyError",
    "DocumentValidationError",
    "TermConflictError",
    "TrainingError",
    "RetrievalError",
    "ModelNotFoundError",
    "PermissionError",
    "ResourceNotFoundError",
    "ExternalServiceError",
    "RateLimitError",
    "InvalidArgumentError",
    "ERROR_CODES",
    "get_http_status",
    "handle_exception"
]