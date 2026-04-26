"""
错误处理器 - 用户友好的错误提示

提供统一的错误提示接口，将技术错误转换为用户友好的消息。
"""

from PyQt6.QtWidgets import QMessageBox, QWidget
from PyQt6.QtCore import Qt
from enum import Enum
from typing import Optional, Dict, Any
import traceback
import logging

logger = logging.getLogger(__name__)


class ErrorLevel(Enum):
    """错误级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCode(Enum):
    """错误代码"""
    # 通用错误
    UNKNOWN_ERROR = "ERR_000"
    NETWORK_ERROR = "ERR_001"
    TIMEOUT_ERROR = "ERR_002"
    PERMISSION_DENIED = "ERR_003"

    # 认证错误
    AUTH_FAILED = "AUTH_001"
    AUTH_EXPIRED = "AUTH_002"
    AUTH_REQUIRED = "AUTH_003"

    # 数据错误
    DATA_NOT_FOUND = "DATA_001"
    DATA_INVALID = "DATA_002"
    DATA_CONFLICT = "DATA_003"

    # 系统错误
    SYSTEM_BUSY = "SYS_001"
    SYSTEM_MAINTENANCE = "SYS_002"
    SYSTEM_ERROR = "SYS_003"

    # 文件错误
    FILE_NOT_FOUND = "FILE_001"
    FILE_ACCESS_DENIED = "FILE_002"
    FILE_CORRUPTED = "FILE_003"

    # 网络错误
    SERVER_UNREACHABLE = "NET_001"
    API_ERROR = "NET_002"
    SYNC_FAILED = "NET_003"


class ErrorHandler:
    """
    错误处理器

    功能：
    1. 将技术错误转换为用户友好的消息
    2. 提供统一的错误提示界面
    3. 记录错误日志
    4. 支持错误重试
    """

    # 用户友好的错误消息映射
    USER_FRIENDLY_MESSAGES: Dict[str, str] = {
        ErrorCode.UNKNOWN_ERROR: "抱歉，发生了一个未知错误。请稍后重试。",
        ErrorCode.NETWORK_ERROR: "网络连接失败，请检查您的网络设置。",
        ErrorCode.TIMEOUT_ERROR: "操作超时，请稍后重试。",
        ErrorCode.PERMISSION_DENIED: "权限不足，无法完成此操作。",

        ErrorCode.AUTH_FAILED: "用户名或密码错误，请重试。",
        ErrorCode.AUTH_EXPIRED: "登录已过期，请重新登录。",
        ErrorCode.AUTH_REQUIRED: "请先登录后再进行操作。",

        ErrorCode.DATA_NOT_FOUND: "请求的数据不存在或已被删除。",
        ErrorCode.DATA_INVALID: "数据格式不正确，请检查输入。",
        ErrorCode.DATA_CONFLICT: "数据冲突，请刷新后重试。",

        ErrorCode.SYSTEM_BUSY: "系统繁忙，请稍后再试。",
        ErrorCode.SYSTEM_MAINTENANCE: "系统维护中，请稍后访问。",
        ErrorCode.SYSTEM_ERROR: "系统错误，请联系管理员。",

        ErrorCode.FILE_NOT_FOUND: "文件不存在，请检查文件路径。",
        ErrorCode.FILE_ACCESS_DENIED: "无法访问文件，请检查文件权限。",
        ErrorCode.FILE_CORRUPTED: "文件已损坏，无法读取。",

        ErrorCode.SERVER_UNREACHABLE: "服务器无法连接，请检查服务器状态。",
        ErrorCode.API_ERROR: "API调用失败，请稍后重试。",
        ErrorCode.SYNC_FAILED: "数据同步失败，请检查网络连接。",
    }

    @classmethod
    def show_error(
        cls,
        parent: Optional[QWidget],
        error: Any,
        level: ErrorLevel = ErrorLevel.ERROR,
        details: str = "",
        retry_callback: Optional[callable] = None
    ):
        """
        显示错误提示

        Args:
            parent: 父窗口
            error: 错误对象（可以是Exception、ErrorCode、或字符串）
            level: 错误级别
            details: 详细信息（可选）
            retry_callback: 重试回调（可选）
        """
        # 获取用户友好的错误消息
        user_message = cls._get_user_message(error)
        technical_details = cls._get_technical_details(error, details)

        # 记录日志
        cls._log_error(error, technical_details)

        # 显示对话框
        if level == ErrorLevel.INFO:
            QMessageBox.information(parent, "提示", user_message)
        elif level == ErrorLevel.WARNING:
            msg_box = QMessageBox(parent)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("警告")
            msg_box.setText(user_message)
            if technical_details:
                msg_box.setDetailedText(technical_details)
            msg_box.exec()
        elif level == ErrorLevel.ERROR:
            msg_box = QMessageBox(parent)
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("错误")
            msg_box.setText(user_message)

            if retry_callback:
                retry_btn = msg_box.addButton("重试", QMessageBox.ButtonRole.AcceptRole)
                cancel_btn = msg_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
                msg_box.setDefaultButton(retry_btn)

                if technical_details:
                    msg_box.setDetailedText(technical_details)

                result = msg_box.exec()
                if result == QMessageBox.ButtonRole.AcceptRole:
                    retry_callback()
            else:
                if technical_details:
                    msg_box.setDetailedText(technical_details)
                msg_box.exec()
        elif level == ErrorLevel.CRITICAL:
            msg_box = QMessageBox(parent)
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("严重错误")
            msg_box.setText(user_message)
            msg_box.setInformativeText("建议保存当前工作并重启应用。")
            if technical_details:
                msg_box.setDetailedText(technical_details)
            msg_box.exec()

    @classmethod
    def _get_user_message(cls, error: Any) -> str:
        """获取用户友好的错误消息"""
        if isinstance(error, ErrorCode):
            return cls.USER_FRIENDLY_MESSAGES.get(
                error,
                cls.USER_FRIENDLY_MESSAGES[ErrorCode.UNKNOWN_ERROR]
            )
        elif isinstance(error, Exception):
            # 根据异常类型返回友好消息
            error_type = type(error).__name__
            if "Connection" in error_type or "Timeout" in error_type:
                return cls.USER_FRIENDLY_MESSAGES[ErrorCode.NETWORK_ERROR]
            elif "Permission" in error_type:
                return cls.USER_FRIENDLY_MESSAGES[ErrorCode.PERMISSION_DENIED]
            elif "FileNotFound" in error_type:
                return cls.USER_FRIENDLY_MESSAGES[ErrorCode.FILE_NOT_FOUND]
            else:
                return str(error)
        elif isinstance(error, str):
            return error
        else:
            return cls.USER_FRIENDLY_MESSAGES[ErrorCode.UNKNOWN_ERROR]

    @classmethod
    def _get_technical_details(cls, error: Any, additional_details: str = "") -> str:
        """获取技术详细信息"""
        details = []

        if isinstance(error, Exception):
            details.append(f"错误类型: {type(error).__name__}")
            details.append(f"错误信息: {str(error)}")
            details.append(f"追踪信息:\n{traceback.format_exc()}")

        if additional_details:
            details.append(f"详细信息:\n{additional_details}")

        return "\n\n".join(details) if details else ""

    @classmethod
    def _log_error(cls, error: Any, technical_details: str):
        """记录错误日志"""
        if isinstance(error, ErrorCode):
            logger.error(f"[{error.value}] {cls.USER_FRIENDLY_MESSAGES.get(error, '')}")
        elif isinstance(error, Exception):
            logger.error(f"[{type(error).__name__}] {str(error)}")
            logger.error(f"Details: {technical_details}")
        else:
            logger.error(f"Unknown error: {error}")

    @classmethod
    def handle_exception(
        cls,
        parent: Optional[QWidget],
        exception: Exception,
        context: str = "",
        retry_callback: Optional[callable] = None
    ):
        """
        处理异常

        Args:
            parent: 父窗口
            exception: 异常对象
            context: 上下文描述
            retry_callback: 重试回调
        """
        details = f"上下文: {context}" if context else ""
        cls.show_error(
            parent,
            exception,
            level=ErrorLevel.ERROR,
            details=details,
            retry_callback=retry_callback
        )

    @classmethod
    def show_network_error(cls, parent: Optional[QWidget], retry_callback: Optional[callable] = None):
        """显示网络错误"""
        cls.show_error(
            parent,
            ErrorCode.NETWORK_ERROR,
            level=ErrorLevel.WARNING,
            retry_callback=retry_callback
        )

    @classmethod
    def show_auth_error(cls, parent: Optional[QWidget]):
        """显示认证错误"""
        cls.show_error(
            parent,
            ErrorCode.AUTH_FAILED,
            level=ErrorLevel.WARNING
        )

    @classmethod
    def show_permission_error(cls, parent: Optional[QWidget]):
        """显示权限错误"""
        cls.show_error(
            parent,
            ErrorCode.PERMISSION_DENIED,
            level=ErrorLevel.WARNING
        )

    @classmethod
    def show_data_not_found(cls, parent: Optional[QWidget], resource: str = "数据"):
        """显示数据不存在错误"""
        cls.show_error(
            parent,
            f"{resource}不存在或已被删除。",
            level=ErrorLevel.INFO
        )


def show_error_message(
    parent: Optional[QWidget],
    message: str,
    level: str = "error"
):
    """
    显示错误信息的简便函数

    Args:
        parent: 父窗口
        message: 错误信息
        level: 错误级别 ("info", "warning", "error", "critical")
    """
    if level == "info":
        QMessageBox.information(parent, "提示", message)
    elif level == "warning":
        QMessageBox.warning(parent, "警告", message)
    elif level == "error":
        QMessageBox.critical(parent, "错误", message)
    elif level == "critical":
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("严重错误")
        msg_box.setText(message)
        msg_box.exec()


def handle_error(
    parent: Optional[QWidget],
    error: Any,
    context: str = "",
    retry_callback: Optional[callable] = None
):
    """
    处理错误的简便函数

    Args:
        parent: 父窗口
        error: 错误对象
        context: 上下文
        retry_callback: 重试回调
    """
    if isinstance(error, Exception):
        ErrorHandler.handle_exception(parent, error, context, retry_callback)
    else:
        ErrorHandler.show_error(parent, error, retry_callback=retry_callback)
