# core/flash_listing/__init__.py
# 对话式闪电上架模块
#
# 从"人找货"到"货找人"的秒级转化
# 五步从图片到可售商品
#
# 代号：引力波探测器 (Graviton Sensor)
# 寓意：捕捉微弱的交易意图涟漪，提前感知需求

__version__ = "1.0.0"

# 核心引擎
from .flash_listing_engine import (
    FlashListingEngine,
    get_flash_listing_engine,
    reset_flash_listing_engine,
    quick_listing,
)

# 数据模型
from .models import (
    # 枚举
    ListingStage,
    ProductCondition,
    DeliveryType,
    PaymentMethod,
    PurchaseStatus,
    # 数据类
    ImageFeature,
    GeneratedListing,
    ProductLink,
    InlinePurchase,
    FulfillmentRecord,
    FlashListingSession,
    # 工具函数
    check_banned_content,
    infer_category,
    BANNED_KEYWORDS,
    CATEGORY_KEYWORDS,
)

# 子模块
from .vision_analyzer import (
    VisionAnalyzer,
    analyze_product_image,
    analyze_product_images,
)

from .listing_generator import (
    ListingGenerator,
    generate_listing,
)

from .product_link import (
    ProductLinkGenerator,
    ProductLink,
    create_product_link,
    create_clickable_text,
    create_markdown_card,
)

from .inline_purchase import (
    InlinePurchaseManager,
    PaymentRouter,
    create_purchase_order,
    initiate_payment,
)

from .fulfillment import (
    FulfillmentManager,
    SimpleLogisticsTracker,
    create_fulfillment,
    submit_shipping,
    confirm_receipt,
    rate_transaction,
)

__all__ = [
    # 版本
    "__version__",
    # 核心引擎
    "FlashListingEngine",
    "get_flash_listing_engine",
    "reset_flash_listing_engine",
    "quick_listing",
    # 枚举
    "ListingStage",
    "ProductCondition",
    "DeliveryType",
    "PaymentMethod",
    "PurchaseStatus",
    # 数据模型
    "ImageFeature",
    "GeneratedListing",
    "ProductLink",
    "InlinePurchase",
    "FulfillmentRecord",
    "FlashListingSession",
    # 工具函数
    "check_banned_content",
    "infer_category",
    "BANNED_KEYWORDS",
    "CATEGORY_KEYWORDS",
    # 子模块
    "VisionAnalyzer",
    "analyze_product_image",
    "analyze_product_images",
    "ListingGenerator",
    "generate_listing",
    "ProductLinkGenerator",
    "create_product_link",
    "create_clickable_text",
    "create_markdown_card",
    "InlinePurchaseManager",
    "PaymentRouter",
    "create_purchase_order",
    "initiate_payment",
    "FulfillmentManager",
    "SimpleLogisticsTracker",
    "create_fulfillment",
    "submit_shipping",
    "confirm_receipt",
    "rate_transaction",
]
