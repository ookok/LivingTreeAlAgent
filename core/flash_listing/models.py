# core/flash_listing/models.py
# 对话式闪电上架 - 核心数据模型
#
# 五步从图片到可售商品：
# 1. 📸 图片特征提取与理解（AI视觉）
# 2. 📝 AI 生成商品资料
# 3. 🏷️ 生成商品标签（伪域名承载）
# 4. 🤝 聊天内嵌购买
# 5. 📦 履约与信任闭环

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import hashlib
import json


# ========== 枚举定义 ==========

class ListingStage(Enum):
    """上架阶段"""
    RAW_IMAGE = "raw_image"           # 原始图片
    FEATURE_EXTRACTED = "feature_extracted"  # 特征已提取
    GENERATED = "generated"           # AI资料已生成
    PUBLISHED = "published"           # 已发布
    MATCHED = "matched"               # 已匹配
    NEGOTIATING = "negotiating"       # 协商中
    AGREED = "agreed"                # 已达成
    PAID = "paid"                    # 已付款
    SHIPPED = "shipped"              # 已发货
    COMPLETED = "completed"           # 已完成
    CANCELLED = "cancelled"          # 已取消


class ProductCondition(Enum):
    """商品成色"""
    NEW = "new"                      # 全新
    LIKE_NEW = "like_new"            # 几乎全新
    USED_GOOD = "used_good"           # 二手-好
    USED_FAIR = "used_fair"          # 二手-一般
    REFURBISHED = "refurbished"      # 翻新


class DeliveryType(Enum):
    """交货方式"""
    FACE_TO_FACE = "face_to_face"    # 面交
    EXPRESS = "express"               # 快递
    LOGISTICS = "logistics"          # 物流
    DOWNLOAD = "download"             # 下载/数字
    SERVICE = "service"              # 服务


class PaymentMethod(Enum):
    """支付方式"""
    WECHAT_PAY = "wechat_pay"         # 微信支付
    ALIPAY = "alipay"                 # 支付宝
    BANK_TRANSFER = "bank_transfer"   # 银行转账
    CRYPTO = "crypto"                 # 加密货币
    ESCROW = "escrow"                # 担保交易
    COD = "cod"                      # 货到付款


class PurchaseStatus(Enum):
    """购买状态"""
    CART = "cart"                    # 加购
    PENDING_PAYMENT = "pending_payment"  # 待付款
    PAID = "paid"                    # 已付款
    PENDING_SHIPMENT = "pending_shipment"  # 待发货
    SHIPPED = "shipped"              # 已发货
    CONFIRMED = "confirmed"          # 已确认收货
    REFUNDED = "refunded"            # 已退款
    CANCELLED = "cancelled"          # 已取消


# ========== 图片特征 ==========

@dataclass
class ImageFeature:
    """图片特征 - AI视觉提取"""

    feature_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    # 品类识别
    category: str = ""                                        # "工矿灯"、"轴承"
    category_confidence: float = 0.0                           # 置信度 0-1

    # 关键属性
    material: Optional[str] = None                             # 材质：金属/塑料
    size_estimate: Optional[str] = None                        # 尺寸估算
    interface_type: Optional[str] = None                       # 接口：螺纹/卡扣
    application: Optional[str] = None                           # 适用场景

    # OCR 提取（若有铭牌/标签）
    ocr_text: Optional[str] = None                             # OCR 识别文本
    model_number: Optional[str] = None                          # 型号
    power_rating: Optional[str] = None                          # 功率
    voltage: Optional[str] = None                              # 电压

    # 原始数据
    original_image_path: str = ""                              # 原始图片路径
    thumbnail_path: Optional[str] = None                        # 缩略图路径

    # 特征向量（用于相似商品匹配）
    feature_vector: Optional[List[float]] = None

    # 元数据
    width: int = 0
    height: int = 0
    format: str = ""

    def to_dict(self) -> Dict:
        return {
            "feature_id": self.feature_id,
            "category": self.category,
            "category_confidence": self.category_confidence,
            "material": self.material,
            "size_estimate": self.size_estimate,
            "interface_type": self.interface_type,
            "application": self.application,
            "ocr_text": self.ocr_text,
            "model_number": self.model_number,
            "power_rating": self.power_rating,
            "voltage": self.voltage,
            "original_image_path": self.original_image_path,
            "thumbnail_path": self.thumbnail_path,
            "width": self.width,
            "height": self.height,
            "format": self.format,
        }


# ========== AI 商品资料 ==========

@dataclass
class GeneratedListing:
    """AI 生成的商品资料"""

    listing_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    # AI 生成的标题和描述
    title: str = ""                                            # 标题（<=20字）
    description: str = ""                                      # 描述（3行）
    key_attributes: Dict[str, str] = field(default_factory=dict)  # 关键参数表

    # 用户补充
    price: Optional[float] = None                              # 价格
    quantity: Optional[int] = None                             # 数量
    condition: ProductCondition = ProductCondition.NEW

    # 交货方式
    delivery_options: List[DeliveryType] = field(default_factory=list)

    # 支付方式
    payment_options: List[PaymentMethod] = field(default_factory=list)

    # 原始特征
    source_features: Optional[ImageFeature] = None

    # 伪域名链接
    product_link: str = ""                                     # product.node8848.tree/item_abc123

    # 状态
    stage: ListingStage = ListingStage.RAW_IMAGE

    # 时间戳
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    expires_at: Optional[float] = None                        # 过期时间

    def to_product_dict(self) -> Dict:
        """转换为 Product 格式"""
        return {
            "product_id": self.listing_id,
            "title": self.title,
            "description": self.description,
            "price": int((self.price or 0) * 100),  # 转为分
            "attributes": self.key_attributes,
            "condition": self.condition.value,
            "delivery_options": [d.value for d in self.delivery_options],
            "payment_options": [p.value for p in self.payment_options],
            "product_link": self.product_link,
        }

    def to_broadcast_dict(self) -> Dict:
        """转换为广播格式"""
        return {
            "listing_id": self.listing_id,
            "title": self.title[:50],
            "price": f"{self.price:.2f}元" if self.price else "待定价",
            "category": self.source_features.category if self.source_features else "other",
            "geo_hash": "",  # 后续添加位置
            "condition": self.condition.value,
            "product_link": self.product_link,
        }


# ========== 商品标签 ==========

@dataclass
class ProductLink:
    """商品伪域名标签"""

    link_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    # 链接信息
    full_link: str = ""                                        # product.node8848.tree/item_abc123
    short_code: str = ""                                       # 短码 item_abc123
    qr_code_data: Optional[str] = None                          # QR码数据

    # 所属节点
    node_id: str = ""                                          # 节点ID
    seller_id: str = ""                                        # 卖家ID

    # 关联商品
    listing_id: str = ""                                        # 商品ID

    # 统计
    click_count: int = 0                                       # 点击次数
    view_count: int = 0                                        # 查看次数

    # 状态
    is_active: bool = True
    is_blacklisted: bool = False                               # 是否被封禁

    # 时间戳
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    expires_at: Optional[float] = None                        # 过期时间

    @property
    def display_text(self) -> str:
        """显示文案"""
        return f"[🛒 查看商品：{self.short_code}]"

    @property
    def clickable_link(self) -> str:
        """可点击链接"""
        return f"product.{self.node_id}.tree/{self.short_code}"


# ========== 内嵌购买 ==========

@dataclass
class InlinePurchase:
    """聊天内嵌购买"""

    purchase_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    # 关联
    listing_id: str = ""
    buyer_id: str = ""
    seller_id: str = ""

    # 商品信息（冗余存储，避免频繁查询）
    product_title: str = ""
    product_link: str = ""
    product_image: Optional[str] = None

    # 价格
    listed_price: float = 0.0                                  #标价
    negotiated_price: Optional[float] = None                   # 协商价

    # 收货信息（加密）
    shipping_address: Optional[str] = None                     # 收货地址
    invoice_info: Optional[str] = None                          # 发票信息

    # 支付
    selected_payment: PaymentMethod = PaymentMethod.ESCROW
    payment_status: PurchaseStatus = PurchaseStatus.CART

    # 订单哈希（存证）
    order_hash: str = ""

    # 时间戳
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    paid_at: Optional[float] = None
    shipped_at: Optional[float] = None
    confirmed_at: Optional[float] = None

    def compute_order_hash(self) -> str:
        """计算订单哈希"""
        data = {
            "purchase_id": self.purchase_id,
            "listing_id": self.listing_id,
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "price": self.negotiated_price or self.listed_price,
            "created_at": self.created_at,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:24]


# ========== 履约记录 ==========

@dataclass
class FulfillmentRecord:
    """履约记录"""

    record_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    # 关联
    purchase_id: str = ""
    listing_id: str = ""

    # 物流
    tracking_number: Optional[str] = None                      # 物流单号
    carrier: Optional[str] = None                               # 承运商

    # 状态
    status: str = "pending"                                    # pending/shipped/delivered/confirmed

    # 买家确认
    buyer_confirmed: bool = False
    confirmed_at: Optional[float] = None

    # 超时自动放款（小时）
    auto_confirm_hours: int = 72

    # 评价
    buyer_rating: Optional[float] = None                       # 买家评价 1-5
    buyer_comment: Optional[str] = None
    buyer_tags: List[str] = field(default_factory=list)         # ["准时", "货真价实"]

    seller_rating: Optional[float] = None                      # 卖家评价 1-5
    seller_comment: Optional[str] = None

    # 时间戳
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())

    def to_credential_dict(self) -> Dict:
        """转换为信用凭证格式"""
        return {
            "deal_id": self.purchase_id,
            "rating": self.buyer_rating or 0,
            "comment": self.buyer_comment or "",
            "tags": self.buyer_tags,
            "timestamp": self.confirmed_at or datetime.now().timestamp(),
        }


# ========== 闪电上架会话 ==========

@dataclass
class FlashListingSession:
    """闪电上架会话"""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    # 用户
    user_id: str = ""
    node_id: str = ""

    # 阶段
    current_stage: ListingStage = ListingStage.RAW_IMAGE

    # 数据
    uploaded_images: List[str] = field(default_factory=list)   # 上传的图片路径
    extracted_features: List[ImageFeature] = field(default_factory=list)  # 提取的特征
    generated_listing: Optional[GeneratedListing] = None       # AI生成的商品资料
    product_link: Optional[ProductLink] = None                  # 商品标签

    # 用户确认
    user_confirmed: bool = False                               # 用户已确认关键参数
    user_edited_title: Optional[str] = None                     # 用户修改的标题
    user_edited_price: Optional[float] = None                  # 用户修改的价格
    user_edited_quantity: Optional[int] = None                  # 用户修改的数量

    # 错误
    error_message: Optional[str] = None
    is_blocked: bool = False                                   # 被封禁（检测到违禁品）

    # 时间戳
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())

    @property
    def progress_percent(self) -> int:
        """进度百分比"""
        stage_order = [
            ListingStage.RAW_IMAGE,
            ListingStage.FEATURE_EXTRACTED,
            ListingStage.GENERATED,
            ListingStage.PUBLISHED,
        ]
        try:
            idx = stage_order.index(self.current_stage)
            return int((idx + 1) / len(stage_order) * 100)
        except ValueError:
            return 0

    @property
    def can_publish(self) -> bool:
        """是否可以发布"""
        return (
            self.current_stage == ListingStage.GENERATED
            and self.user_confirmed
            and not self.is_blocked
            and self.generated_listing is not None
        )


# ========== 违禁品检测 ==========

BANNED_KEYWORDS = [
    # 武器类
    "枪", "枪支", "弹药", "炸弹", "雷管", "手榴弹", "刀", "匕首",
    # 毒品类
    "毒品", "大麻", "海洛因", "冰毒", "K粉",
    # 伪造类
    "假证", "假币", "伪造",
    # 其他
    "人体器官",
]


def check_banned_content(title: str, description: str, features: ImageFeature) -> tuple:
    """
    检查违禁内容
    Returns: (is_banned: bool, reason: str)
    """
    all_text = f"{title} {description}"
    if features.ocr_text:
        all_text += f" {features.ocr_text}"
    if features.category:
        all_text += f" {features.category}"

    for keyword in BANNED_KEYWORDS:
        if keyword in all_text:
            return True, f"包含违禁关键词：{keyword}"

    return False, ""


# ========== 品类映射 ==========

CATEGORY_KEYWORDS = {
    "electronics": ["灯", "电机", "电线", "电池", "电子", "芯片", "LED", "电源"],
    "machinery": ["轴承", "齿轮", "螺丝", "螺母", "螺栓", "法兰", "联轴器", "减速机"],
    "plastic": ["塑料", "ABS", "PVC", "PE", "PP", "塑料粒子", "树脂"],
    "metal": ["钢材", "铜", "铝", "铁", "不锈钢", "铝合金", "铜合金"],
    "chemical": ["化学", "溶剂", "原料", "助剂"],
    "textile": ["布料", "面料", "纱线", "纤维", "纺织"],
    "food": ["食品", "农产品", "粮油", "调料"],
    "service": ["服务", "维修", "加工", "定制"],
}


def infer_category(keywords: List[str]) -> tuple:
    """从关键词推断品类"""
    scores = {}
    for category, cat_keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if any(ck in kw for ck in cat_keywords))
        if score > 0:
            scores[category] = score

    if not scores:
        return "other", 0.0

    best = max(scores.items(), key=lambda x: x[1])
    return best[0], min(best[1] / len(keywords), 1.0)
