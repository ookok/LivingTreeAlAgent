"""
项目财务管理模块

管理咨询项目的报价、合同、发票、回款等财务流程。
"""

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime, timedelta


# ==================== 枚举定义 ====================

class QuotationStatus(Enum):
    """报价状态"""
    DRAFT = "draft"
    SENT = "sent"
    NEGOTIATING = "negotiating"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class InvoiceStatus(Enum):
    """发票状态"""
    DRAFT = "draft"
    ISSUED = "issued"
    SENT = "sent"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class PaymentStatus(Enum):
    """付款状态"""
    PENDING = "pending"
    PARTIAL = "partial"
    COMPLETED = "completed"
    OVERDUE = "overdue"


class TaxRate(Enum):
    """税率"""
    VAT_6 = 0.06
    VAT_9 = 0.09
    VAT_13 = 0.13


# ==================== 数据模型 ====================

@dataclass
class PriceComponent:
    """价格组成部分"""
    component_id: str
    name: str
    description: str = ""
    quantity: float = 1.0
    unit: str = "项"
    unit_price: float = 0.0
    subtotal: float = 0.0
    discount: float = 0.0
    tax_rate: float = 0.0
    tax_amount: float = 0.0
    total: float = 0.0


@dataclass
class QuotationItem:
    """报价明细项"""
    item_id: str
    category: str                      # 咨询/编制/评审/其他
    item_name: str
    description: str = ""

    # 数量和价格
    quantity: float = 1.0
    unit: str = "项"
    unit_price: float = 0.0

    # 折扣
    discount_percent: float = 0.0      # 折扣百分比
    discount_amount: float = 0.0        # 折扣金额

    # 计算
    subtotal: float = 0.0              # 小计
    tax_rate: float = 0.06             # 税率
    tax_amount: float = 0.0            # 税额
    total: float = 0.0                 # 合计

    def calculate(self):
        """计算金额"""
        self.subtotal = self.quantity * self.unit_price
        if self.discount_percent > 0:
            self.discount_amount = self.subtotal * self.discount_percent / 100
        self.subtotal -= self.discount_amount
        self.tax_amount = self.subtotal * self.tax_rate
        self.total = self.subtotal + self.tax_amount


@dataclass
class Quotation:
    """报价单"""
    quotation_id: str
    quotation_code: str

    # 关联
    project_id: str = ""
    client_id: str = ""
    client_name: str = ""

    # 报价内容
    items: List[QuotationItem] = field(default_factory=list)

    # 金额汇总
    subtotal: float = 0.0
    total_discount: float = 0.0
    total_tax: float = 0.0
    total_amount: float = 0.0

    # 有效期
    valid_from: datetime = field(default_factory=datetime.now)
    valid_until: datetime = None

    # 状态
    status: QuotationStatus = QuotationStatus.DRAFT

    # 备注
    notes: str = ""
    payment_terms: str = ""            # 付款条款
    delivery_terms: str = ""          # 交付条款

    # 审批
    approved_by: str = ""
    approved_at: Optional[datetime] = None

    # 元数据
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Invoice:
    """发票"""
    invoice_id: str
    invoice_code: str                  # 发票号
    invoice_type: str = "增值税专用发票"  # 发票类型

    # 关联
    project_id: str = ""
    client_id: str = ""
    quotation_id: str = ""

    # 发票内容
    items: List[Dict] = field(default_factory=list)  # 开票明细

    # 金额
    subtotal: float = 0.0
    tax_rate: float = 0.06
    tax_amount: float = 0.0
    total_amount: float = 0.0

    # 收票人信息
    buyer_name: str = ""
    buyer_tax_number: str = ""         # 购买方税号
    buyer_address: str = ""
    buyer_phone: str = ""
    buyer_bank: str = ""
    buyer_account: str = ""

    # 开票人信息
    seller_name: str = ""
    seller_tax_number: str = ""

    # 状态
    status: InvoiceStatus = InvoiceStatus.DRAFT

    # 时间
    issue_date: Optional[datetime] = None
    sent_date: Optional[datetime] = None
    confirmed_date: Optional[datetime] = None

    # 元数据
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class PaymentRecord:
    """付款记录"""
    payment_id: str
    payment_date: datetime
    amount: float

    # 关联
    project_id: str = ""
    client_id: str = ""

    # 付款信息
    payment_method: str = ""          # 银行转账/现金/支票
    payment_reference: str = ""       # 付款凭证号

    # 对应的发票/应收
    invoiced_amount: float = 0.0      # 已开票金额
    received_amount: float = 0.0      # 已收款金额
    outstanding_amount: float = 0.0   # 欠款金额

    # 状态
    status: PaymentStatus = PaymentStatus.PENDING

    # 备注
    notes: str = ""

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ProjectFinance:
    """项目财务总览"""
    project_id: str

    # 合同信息
    contract_amount: float = 0.0
    contract_date: Optional[datetime] = None

    # 已开票
    total_invoiced: float = 0.0
    invoice_count: int = 0

    # 已收款
    total_received: float = 0.0
    payment_count: int = 0

    # 欠款
    outstanding_amount: float = 0.0

    # 回款率
    payment_rate: float = 0.0         # 已收款/合同金额

    # 付款计划
    payment_schedule: List[Dict] = field(default_factory=list)


# ==================== 报价引擎 ====================

class QuotationEngine:
    """
    智能报价引擎

    基于项目特征自动生成报价
    """

    # 基础价格表
    BASE_PRICES = {
        "eia_report": {
            "small": 50000,    # 小型项目
            "medium": 80000,   # 中型项目
            "large": 150000,   # 大型项目
        },
        "safety_assessment": {
            "small": 30000,
            "medium": 50000,
            "large": 100000,
        },
        "feasibility_study": {
            "small": 20000,
            "medium": 40000,
            "large": 80000,
        },
        "pollution_permit": {
            "small": 15000,
            "medium": 25000,
            "large": 50000,
        },
        "emergency_plan": {
            "small": 10000,
            "medium": 20000,
            "large": 40000,
        },
    }

    # 难度系数
    DIFFICULTY_FACTORS = {
        "industry_risk_high": 1.3,     # 高风险行业
        "chemical": 1.3,
        "pharmaceutical": 1.2,
        "electronics": 1.0,
        "manufacturing": 1.0,

        "region_complexity": {
            "北京": 1.3,
            "上海": 1.2,
            "广东": 1.1,
            "江苏": 1.0,
            "其他": 0.9,
        },

        "project_scale": {
            "small": 1.0,      # < 1000万投资
            "medium": 1.2,    # 1000万-1亿
            "large": 1.5,     # > 1亿
        }
    }

    # 附加服务价格
    ADDITIONAL_SERVICES = {
        "expert_review": 5000,          # 专家评审
        "on_site_investigation": 3000,  # 现场勘查
        "monitoring": 10000,            # 监测服务
        "urgent": 1.5,                  # 加急系数
        "translation": 2000,            # 翻译服务
    }

    @classmethod
    def estimate_price(
        cls,
        project_type: str,
        industry: str = None,
        region: str = "江苏",
        scale: str = "medium",
        investment_amount: float = 0.0,
        additional_services: List[str] = None,
        is_urgent: bool = False
    ) -> Dict:
        """
        估算价格

        Args:
            project_type: 项目类型
            industry: 行业
            region: 地区
            scale: 规模
            investment_amount: 投资额
            additional_services: 附加服务
            is_urgent: 是否加急

        Returns:
            估算结果
        """
        # 获取基础价格
        base_prices = cls.BASE_PRICES.get(project_type, {})
        base_price = base_prices.get(scale, 50000)

        # 计算难度系数
        difficulty_factor = 1.0

        # 行业难度
        if industry in ["chemical", "petrochemical", "pharmaceutical"]:
            difficulty_factor *= 1.3
        elif industry in ["electronics", "machinery"]:
            difficulty_factor *= 1.0
        else:
            difficulty_factor *= 1.1

        # 地区难度
        region_factor = cls.DIFFICULTY_FACTORS["region_complexity"].get(region, 1.0)
        difficulty_factor *= region_factor

        # 项目规模（基于投资额）
        if investment_amount > 100000000:  # > 1亿
            difficulty_factor *= 1.5
        elif investment_amount > 10000000:  # > 1000万
            difficulty_factor *= 1.2

        # 基础费用
        base_fee = base_price * difficulty_factor

        # 附加服务费用
        additional_fee = 0
        if additional_services:
            for service in additional_services:
                if service in cls.ADDITIONAL_SERVICES:
                    if isinstance(cls.ADDITIONAL_SERVICES[service], (int, float)):
                        additional_fee += cls.ADDITIONAL_SERVICES[service]

        # 加急费用
        urgent_fee = 0
        if is_urgent:
            urgent_fee = base_fee * 0.5

        # 合计
        total = base_fee + additional_fee + urgent_fee

        # 利润率建议（咨询行业一般30-50%）
        profit_margin = 0.35
        final_price = total / (1 - profit_margin)

        return {
            "base_price": base_price,
            "difficulty_factor": difficulty_factor,
            "base_fee": base_fee,
            "additional_fee": additional_fee,
            "urgent_fee": urgent_fee,
            "cost_total": total,
            "suggested_price": round(final_price, 2),
            "price_range": {
                "low": round(final_price * 0.85, 2),
                "medium": round(final_price, 2),
                "high": round(final_price * 1.2, 2),
            },
            "breakdown": {
                "人力成本": round(total * 0.5, 2),
                "差旅成本": round(total * 0.1, 2),
                "管理费用": round(total * 0.15, 2),
                "利润": round(final_price - total, 2),
            }
        }


# ==================== 财务服务 ====================

class FinanceService:
    """
    项目财务管理服务

    核心功能：
    1. 报价管理
    2. 发票管理
    3. 收款管理
    4. 财务报表
    """

    def __init__(self):
        self._quotations: Dict[str, Quotation] = {}
        self._invoices: Dict[str, Invoice] = {}
        self._payments: Dict[str, PaymentRecord] = {}
        self._quotation_counter = 0

    def _generate_quotation_id(self) -> str:
        return f"QT:{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _generate_invoice_id(self) -> str:
        return f"INV:{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _generate_payment_id(self) -> str:
        return f"PAY:{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # ==================== 报价管理 ====================

    async def create_quotation(
        self,
        project_id: str,
        client_id: str,
        client_name: str,
        created_by: str,
        items: List[QuotationItem] = None,
        notes: str = "",
        payment_terms: str = ""
    ) -> Quotation:
        """创建报价单"""
        self._quotation_counter += 1
        quotation_id = self._generate_quotation_id()
        quotation_code = f"QT-{datetime.now().year}-{self._quotation_counter:04d}"

        quotation = Quotation(
            quotation_id=quotation_id,
            quotation_code=quotation_code,
            project_id=project_id,
            client_id=client_id,
            client_name=client_name,
            items=items or [],
            notes=notes,
            payment_terms=payment_terms,
            valid_until=datetime.now() + timedelta(days=30),
            created_by=created_by
        )

        # 计算金额
        self._recalculate_quotation(quotation)

        self._quotations[quotation_id] = quotation
        return quotation

    def _recalculate_quotation(self, quotation: Quotation):
        """重新计算报价单金额"""
        quotation.subtotal = sum(item.total for item in quotation.items)
        quotation.total_tax = sum(item.tax_amount for item in quotation.items)
        quotation.total_amount = quotation.subtotal + quotation.total_tax

    async def add_quotation_item(
        self,
        quotation_id: str,
        item: QuotationItem
    ) -> bool:
        """添加报价明细"""
        quotation = self._quotations.get(quotation_id)
        if not quotation:
            return False

        item.item_id = f"{quotation_id}:ITEM:{len(quotation.items) + 1}"
        item.calculate()

        quotation.items.append(item)
        self._recalculate_quotation(quotation)
        return True

    async def update_quotation_status(
        self,
        quotation_id: str,
        status: QuotationStatus
    ) -> bool:
        """更新报价状态"""
        quotation = self._quotations.get(quotation_id)
        if not quotation:
            return False

        quotation.status = status
        quotation.updated_at = datetime.now()
        return True

    async def accept_quotation(
        self,
        quotation_id: str,
        approved_by: str
    ) -> bool:
        """接受报价"""
        quotation = self._quotations.get(quotation_id)
        if not quotation:
            return False

        quotation.status = QuotationStatus.ACCEPTED
        quotation.approved_by = approved_by
        quotation.approved_at = datetime.now()
        return True

    # ==================== 发票管理 ====================

    async def create_invoice(
        self,
        project_id: str,
        client_id: str,
        quotation_id: str,
        created_by: str,
        items: List[Dict] = None,
        tax_rate: float = 0.06,
        **buyer_info
    ) -> Invoice:
        """创建发票"""
        invoice_id = self._generate_invoice_id()

        # 获取报价单信息
        quotation = self._quotations.get(quotation_id)

        invoice = Invoice(
            invoice_id=invoice_id,
            invoice_code=f"FP{ datetime.now().year }{len(self._invoices) + 1:06d}",
            project_id=project_id,
            client_id=client_id,
            quotation_id=quotation_id,
            items=items or [],
            tax_rate=tax_rate,
            status=InvoiceStatus.DRAFT,
            created_by=created_by,
            **buyer_info
        )

        # 从报价单计算金额
        if quotation:
            invoice.subtotal = quotation.total_amount / (1 + tax_rate)
            invoice.tax_amount = invoice.subtotal * tax_rate
            invoice.total_amount = quotation.total_amount

        self._invoices[invoice_id] = invoice
        return invoice

    async def issue_invoice(self, invoice_id: str) -> bool:
        """开具发票"""
        invoice = self._invoices.get(invoice_id)
        if not invoice:
            return False

        invoice.status = InvoiceStatus.ISSUED
        invoice.issue_date = datetime.now()
        return True

    async def confirm_invoice(self, invoice_id: str) -> bool:
        """确认发票收到"""
        invoice = self._invoices.get(invoice_id)
        if not invoice:
            return False

        invoice.status = InvoiceStatus.CONFIRMED
        invoice.confirmed_date = datetime.now()
        return True

    # ==================== 收款管理 ====================

    async def record_payment(
        self,
        project_id: str,
        client_id: str,
        amount: float,
        payment_date: datetime,
        payment_method: str = "",
        payment_reference: str = "",
        notes: str = ""
    ) -> PaymentRecord:
        """记录收款"""
        payment_id = self._generate_payment_id()

        payment = PaymentRecord(
            payment_id=payment_id,
            payment_date=payment_date,
            amount=amount,
            project_id=project_id,
            client_id=client_id,
            payment_method=payment_method,
            payment_reference=payment_reference,
            notes=notes,
            received_amount=amount
        )

        self._payments[payment_id] = payment

        # 更新项目财务
        await self._update_project_finance(project_id)

        return payment

    async def _update_project_finance(self, project_id: str) -> ProjectFinance:
        """更新项目财务"""
        # TODO: 实际实现
        return ProjectFinance(project_id=project_id)

    # ==================== 财务报表 ====================

    async def get_project_finance(
        self,
        project_id: str
    ) -> Optional[ProjectFinance]:
        """获取项目财务"""
        return await self._update_project_finance(project_id)

    async def get_client_finance_summary(
        self,
        client_id: str
    ) -> Dict:
        """获取客户财务汇总"""
        # 汇总该客户所有项目
        quotations = [q for q in self._quotations.values() if q.client_id == client_id]
        invoices = [i for i in self._invoices.values() if i.client_id == client_id]
        payments = [p for p in self._payments.values() if p.client_id == client_id]

        total_quoted = sum(q.total_amount for q in quotations if q.status == QuotationStatus.ACCEPTED)
        total_invoiced = sum(i.total_amount for i in invoices if i.status == InvoiceStatus.CONFIRMED)
        total_received = sum(p.received_amount for p in payments)

        return {
            "client_id": client_id,
            "project_count": len(set(q.project_id for q in quotations)),
            "quotation_count": len(quotations),
            "accepted_quotation_amount": total_quoted,
            "total_invoiced": total_invoiced,
            "total_received": total_received,
            "outstanding": total_invoiced - total_received,
            "payment_rate": (total_received / total_invoiced * 100) if total_invoiced > 0 else 0
        }


# ==================== 单例模式 ====================

_finance_service: Optional[FinanceService] = None


def get_finance_service() -> FinanceService:
    """获取财务服务单例"""
    global _finance_service
    if _finance_service is None:
        _finance_service = FinanceService()
    return _finance_service
