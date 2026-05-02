# -*- coding: utf-8 -*-
"""
统一佣金系统 - 数据模型层
Unified Commission System - Data Models

定义所有核心数据结构和枚举类型
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class ModuleType(Enum):
    """模块类型枚举"""
    DEEP_SEARCH = "deep_search"
    CREATION = "creation"
    STOCK_FUTURES = "stock_futures"
    GAME = "game"
    IDE = "ide"


class PaymentProvider(Enum):
    """支付提供商枚举"""
    WECHAT = "wechat"
    ALIPAY = "alipay"
    INTERNAL = "internal"


class SettlementStatus(Enum):
    """结算状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RefundStatus(Enum):
    """退款状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class OrderStatus(Enum):
    """订单状态枚举"""
    CREATED = "created"
    PENDING = "pending"
    PAID = "paid"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class TestResult:
    """配置测试结果"""
    def __init__(self, name: str):
        self.name = name
        self.success = False
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.data: Dict[str, Any] = {}
        self.timestamp = datetime.now()
    
    def add_error(self, message: str):
        self.errors.append(message)
    
    def add_warning(self, message: str):
        self.warnings.append(message)
    
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "success": self.success,
            "errors": self.errors,
            "warnings": self.warnings,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ModuleConfig:
    """模块配置"""
    module_type: ModuleType
    enabled: bool = True
    display_name: str = ""
    description: str = ""
    min_amount: float = 1.0
    max_amount: float = 10000.0
    default_amounts: List[float] = field(default_factory=lambda: [10, 20, 50, 100])
    commission_rate: float = 0.0003  # 0.03%
    features: List[str] = field(default_factory=list)
    require_verification: bool = False
    risk_warning: str = ""
    
    @classmethod
    def from_dict(cls, module_type: ModuleType, data: Dict[str, Any]) -> "ModuleConfig":
        return cls(
            module_type=module_type,
            enabled=data.get("enabled", True),
            display_name=data.get("display_name", module_type.value),
            description=data.get("description", ""),
            min_amount=data.get("min_amount", 1.0),
            max_amount=data.get("max_amount", 10000.0),
            default_amounts=data.get("default_amounts", [10, 20, 50, 100]),
            commission_rate=data.get("commission_rate", 0.0003),
            features=data.get("features", []),
            require_verification=data.get("require_verification", False),
            risk_warning=data.get("risk_warning", "")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "display_name": self.display_name,
            "description": self.description,
            "min_amount": self.min_amount,
            "max_amount": self.max_amount,
            "default_amounts": self.default_amounts,
            "commission_rate": self.commission_rate,
            "features": self.features,
            "require_verification": self.require_verification,
            "risk_warning": self.risk_warning
        }


@dataclass
class CommissionResult:
    """佣金计算结果"""
    original_amount: float  # 原始金额
    commission_amount: float  # 佣金金额
    total_amount: float  # 总支付金额
    commission_rate: float  # 佣金比例
    module_type: ModuleType  # 模块类型
    currency: str = "CNY"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_amount": self.original_amount,
            "commission_amount": self.commission_amount,
            "total_amount": self.total_amount,
            "commission_rate": self.commission_rate,
            "module_type": self.module_type.value,
            "currency": self.currency
        }


@dataclass
class PaymentOrder:
    """支付订单"""
    order_id: str = field(default_factory=lambda: f"ORD{uuid.uuid4().hex[:12].upper()}")
    module_type: ModuleType = ModuleType.DEEP_SEARCH
    provider: PaymentProvider = PaymentProvider.WECHAT
    original_amount: float = 0.0
    commission_amount: float = 0.0
    total_amount: float = 0.0
    status: OrderStatus = OrderStatus.CREATED
    subject: str = ""
    body: str = ""
    user_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    paid_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "module_type": self.module_type.value,
            "provider": self.provider.value,
            "original_amount": self.original_amount,
            "commission_amount": self.commission_amount,
            "total_amount": self.total_amount,
            "status": self.status.value,
            "subject": self.subject,
            "body": self.body,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "extra_data": self.extra_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaymentOrder":
        return cls(
            order_id=data.get("order_id", ""),
            module_type=ModuleType(data.get("module_type", "deep_search")),
            provider=PaymentProvider(data.get("provider", "wechat")),
            original_amount=data.get("original_amount", 0.0),
            commission_amount=data.get("commission_amount", 0.0),
            total_amount=data.get("total_amount", 0.0),
            status=OrderStatus(data.get("status", "created")),
            subject=data.get("subject", ""),
            body=data.get("body", ""),
            user_id=data.get("user_id", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            paid_at=datetime.fromisoformat(data["paid_at"]) if data.get("paid_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            extra_data=data.get("extra_data", {})
        )


@dataclass
class Settlement:
    """结算记录"""
    settlement_id: str = field(default_factory=lambda: f"STL{uuid.uuid4().hex[:12].upper()}")
    order_id: str = ""
    module_type: ModuleType = ModuleType.DEEP_SEARCH
    author_amount: float = 0.0  # 作者所得
    developer_amount: float = 0.0  # 开发者佣金
    commission_amount: float = 0.0
    status: SettlementStatus = SettlementStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "settlement_id": self.settlement_id,
            "order_id": self.order_id,
            "module_type": self.module_type.value,
            "author_amount": self.author_amount,
            "developer_amount": self.developer_amount,
            "commission_amount": self.commission_amount,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "notes": self.notes
        }


@dataclass
class Refund:
    """退款记录"""
    refund_id: str = field(default_factory=lambda: f"RFD{uuid.uuid4().hex[:12].upper()}")
    order_id: str = ""
    refund_amount: float = 0.0
    refund_type: str = "USER_CANCEL"  # USER_CANCEL, PAY_TIMEOUT, SYSTEM_ERROR, SERVICE_UNAVAILABLE, OTHER
    reason: str = ""
    status: RefundStatus = RefundStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    operator: str = ""
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "refund_id": self.refund_id,
            "order_id": self.order_id,
            "refund_amount": self.refund_amount,
            "refund_type": self.refund_type,
            "reason": self.reason,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "operator": self.operator,
            "notes": self.notes
        }


@dataclass
class PaymentConfig:
    """支付配置"""
    enabled: bool = True
    default_provider: PaymentProvider = PaymentProvider.WECHAT
    wechat: Dict[str, Any] = field(default_factory=dict)
    alipay: Dict[str, Any] = field(default_factory=dict)
    common: Dict[str, Any] = field(default_factory=lambda: {
        "order_prefix": "COMM",
        "order_timeout": 1800,
        "qr_code_size": 300
    })
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaymentConfig":
        return cls(
            enabled=data.get("enabled", True),
            default_provider=PaymentProvider(data.get("default_provider", "wechat")),
            wechat=data.get("wechat", {}),
            alipay=data.get("alipay", {}),
            common=data.get("common", {
                "order_prefix": "COMM",
                "order_timeout": 1800,
                "qr_code_size": 300
            })
        )


@dataclass
class SettlementConfig:
    """结算配置"""
    developer: Dict[str, Any] = field(default_factory=lambda: {
        "account_id": "developer_001",
        "account_name": "软件开发作者",
        "commission_rate": 0.0003,
        "auto_settlement": True,
        "settlement_threshold": 100.0,
        "settlement_cycle": "weekly",
        "settlement_day": 1
    })
    author: Dict[str, Any] = field(default_factory=lambda: {
        "auto_settlement": True,
        "settlement_threshold": 10.0,
        "settlement_cycle": "monthly",
        "min_withdraw_amount": 1.0,
        "max_withdraw_amount": 50000.0
    })
    methods: List[Dict[str, Any]] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SettlementConfig":
        return cls(
            developer=data.get("developer", {}),
            author=data.get("author", {}),
            methods=data.get("methods", [])
        )


@dataclass
class GlobalConfig:
    """全局配置"""
    app_name: str = "智能创作平台"
    app_version: str = "1.0.0"
    base_currency: str = "CNY"
    commission_rate: float = 0.0003
    min_commission: float = 0.01
    max_order_amount: float = 50000.0
    auto_refund_timeout: int = 1800
    enable_debug_log: bool = False
    log_level: str = "INFO"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlobalConfig":
        return cls(
            app_name=data.get("app_name", "智能创作平台"),
            app_version=data.get("app_version", "1.0.0"),
            base_currency=data.get("base_currency", "CNY"),
            commission_rate=data.get("commission_rate", 0.0003),
            min_commission=data.get("min_commission", 0.01),
            max_order_amount=data.get("max_order_amount", 50000.0),
            auto_refund_timeout=data.get("auto_refund_timeout", 1800),
            enable_debug_log=data.get("enable_debug_log", False),
            log_level=data.get("log_level", "INFO")
        )
