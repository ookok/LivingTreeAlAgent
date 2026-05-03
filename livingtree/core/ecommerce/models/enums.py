"""
统一电商枚举定义

合并自:
- local_market/models.py (NodeType, ProductCategory, TransactionStatus, PaymentType, DeliveryType, ReputationAction, MessageType)
- decommerce/models.py (ServiceType, ServiceStatus, ConnectionQuality)
- flash_listing/models.py (ListingStage, ProductCondition, DeliveryType, PaymentMethod, PurchaseStatus)
- social_commerce/models.py (NodeType, IntentLevel, MatchStrength, GeoPrecision, TradeStatus, CreditAction)
"""

from enum import Enum


# ============================================================================
# 角色类型 — 合并 local_market.NodeType + social_commerce.NodeType
# ============================================================================

class NodeRole(Enum):
    """节点角色（统一）"""
    BUYER = "buyer"           # 买家
    SELLER = "seller"         # 卖家
    BOTH = "both"             # 工贸一体（买+卖）
    WITNESS = "witness"       # 见证节点
    RELAY = "relay"           # 中继节点
    SERVICE = "service"       # 服务商（物流/质检/加工）


# ============================================================================
# 商品/服务分类 — 合并 ProductCategory + ServiceType + CATEGORY_KEYWORDS
# ============================================================================

class ListingCategory(Enum):
    """商品/服务分类（统一）"""
    ELECTRONICS = "electronics"        # 电子产品
    FASHION = "fashion"                # 服饰箱包
    HOME = "home"                      # 家居用品
    FOOD = "food"                      # 食品生鲜
    BOOKS = "books"                    # 图书二手
    VEHICLES = "vehicles"              # 车辆交通工具
    MACHINERY = "machinery"            # 机械设备/工业品
    MATERIAL = "material"              # 原材料（金属/塑料/化工）
    TEXTILE = "textile"                # 纺织面料
    SERVICE = "service"                # 本地服务/加工
    DIGITAL = "digital"                # 数字商品
    AI_COMPUTING = "ai_computing"      # AI计算服务
    KNOWLEDGE = "knowledge"            # 知识咨询
    LIVE = "live"                      # 远程实景/直播
    OTHER = "other"                    # 其他


# ============================================================================
# 商品成色
# ============================================================================

class ProductCondition(Enum):
    """商品成色"""
    NEW = "new"
    LIKE_NEW = "like_new"
    USED_GOOD = "used_good"
    USED_FAIR = "used_fair"
    REFURBISHED = "refurbished"


# ============================================================================
# 交付方式 — 合并 local_market.DeliveryType + flash_listing.DeliveryType
# ============================================================================

class DeliveryMethod(Enum):
    """交付方式（统一）"""
    PICKUP = "pickup"                  # 买家自提/面交
    NODE_DELIVERY = "node_delivery"    # 节点配送
    SAFEPOINT = "safepoint"            # 安全交付点
    EXPRESS = "express"                # 快递
    LOGISTICS = "logistics"            # 大件物流
    DOWNLOAD = "download"              # 下载/数字交付
    INSTANT = "instant"                # 即时服务（P2P直连）
    SCHEDULED = "scheduled"            # 预约服务
    LIVE = "live"                      # 实时流服务


# ============================================================================
# 支付方式 — 合并 local_market.PaymentType + flash_listing.PaymentMethod
# ============================================================================

class PaymentMethod(Enum):
    """支付方式（统一）"""
    DIRECT = "direct"                  # 直接支付
    ESCROW_2OF3 = "escrow_2of3"        # 2/3多签托管
    ESCROW = "escrow"                  # 担保交易
    TIMELOCK = "timelock"              # 时间锁支付
    WECHAT_PAY = "wechat_pay"          # 微信支付
    ALIPAY = "alipay"                  # 支付宝
    BANK_TRANSFER = "bank_transfer"    # 银行转账
    CRYPTO = "crypto"                  # 加密货币
    COD = "cod"                        # 货到付款


# ============================================================================
# 交易/订单状态 — 合并 local_market.TransactionStatus + TradeStatus + PurchaseStatus
# ============================================================================

class OrderStatus(Enum):
    """订单状态（统一）"""
    INITIATED = "initiated"            # 已发起
    NEGOTIATING = "negotiating"        # 协商中
    AGREED = "agreed"                  # 已达成
    PENDING_PAYMENT = "pending_payment"  # 待付款
    PAID = "paid"                      # 已付款
    ESCROW = "escrow"                  # 托管中
    PENDING_SHIPMENT = "pending_shipment"  # 待发货
    SHIPPED = "shipped"                # 已发货
    DELIVERING = "delivering"          # 交付中
    CONFIRMED = "confirmed"            # 已确认收货
    COMPLETED = "completed"            # 已完成
    CANCELLED = "cancelled"            # 已取消
    DISPUTED = "disputed"              # 争议中
    REFUNDED = "refunded"              # 已退款


# ============================================================================
# 商品状态 — 合并 ServiceStatus + Product.status + ListingStage
# ============================================================================

class ListingStatus(Enum):
    """商品/服务状态（统一）"""
    DRAFT = "draft"                    # 草稿
    ONLINE = "online"                  # 在线
    OFFLINE = "offline"                # 下线
    RESERVED = "reserved"              # 已预订
    SOLD = "sold"                      # 已售出
    REMOVED = "removed"                # 已删除
    LIVE_ACTIVE = "live_active"        # 实时服务激活
    LIVE_BUSY = "live_busy"            # 服务中
    LIVE_PAUSED = "live_paused"        # 暂停


# ============================================================================
# 意图强度 — 来自 social_commerce.IntentLevel
# ============================================================================

class IntentLevel(Enum):
    """购买/交易意图强度"""
    NONE = "none"                      # 无意图
    BROWSING = "browsing"              # 浏览中
    COMPARING = "comparing"            # 比价中
    READY = "ready"                    # 准备交易
    URGENT = "urgent"                  # 急需


# ============================================================================
# 匹配强度 — 来自 social_commerce.MatchStrength
# ============================================================================

class MatchStrength(Enum):
    """撮合匹配强度"""
    NONE = "none"
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"
    PERFECT = "perfect"


# ============================================================================
# 地理精度 — 来自 social_commerce.GeoPrecision
# ============================================================================

class GeoPrecision(Enum):
    """地理精度"""
    EXACT = "exact"                    # 精确坐标
    NEIGHBORHOOD = "neighborhood"      # 模糊区域（GeoHash 6位）
    DISTRICT = "district"              # 区县（GeoHash 5位）
    CITY = "city"                      # 城市（GeoHash 4位）


# ============================================================================
# 连接质量 — 来自 decommerce.ConnectionQuality
# ============================================================================

class ConnectionQuality(Enum):
    """P2P连接质量"""
    EXCELLENT = "excellent"            # P2P直连
    GOOD = "good"                      # TURN中继
    FAIR = "fair"                      # 弱网
    POOR = "poor"                      # 勉强可用


# ============================================================================
# 信誉操作 — 来自 local_market.ReputationAction
# ============================================================================

class ReputationAction(Enum):
    """信誉操作"""
    SUCCESSFUL_TRADE = "successful_trade"    # 成功交易
    GOOD_REVIEW = "good_review"              # 好评
    QUICK_CONFIRM = "quick_confirm"          # 快速确认
    DISPUTE_RESOLVE = "dispute_resolve"      # 纠纷和解
    TRADE_CANCEL = "trade_cancel"            # 交易取消
    BAD_REVIEW = "bad_review"                # 差评
    FALSE_PRODUCT = "false_product"          # 虚假商品
    FRAUD = "fraud"                          # 欺诈


# ============================================================================
# 信用行为 — 来自 social_commerce.CreditAction
# ============================================================================

class CreditAction(Enum):
    """信用行为"""
    LISTING = "listing"                # 上架商品
    VIEWING = "viewing"                # 查看商品
    INQUIRY = "inquiry"                # 询价
    NEGOTIATION = "negotiation"        # 协商
    DEAL = "deal"                      # 成交
    RATING = "rating"                  # 评价
    REFERRAL = "referral"              # 推荐


# ============================================================================
# 网络消息类型 — 来自 local_market.MessageType
# ============================================================================

class MessageType(Enum):
    """P2P网络消息类型"""
    DISCOVERY = "discovery"            # 商品发现广播
    PRODUCT_QUERY = "product_query"    # 商品查询
    TRADE_REQUEST = "trade_request"    # 交易请求
    CHAT = "chat"                      # 聊天消息
    TRADE_UPDATE = "trade_update"      # 交易状态更新
    REPUTATION = "reputation"          # 信誉事件广播
    ARBITRATION = "arbitration"        # 仲裁消息
    HEARTBEAT = "heartbeat"            # 心跳检测
    RELAY = "relay"                    # 中继消息


# ============================================================================
# 争议类别
# ============================================================================

class DisputeCategory(Enum):
    """争议类别"""
    QUALITY = "quality"                # 质量问题
    NON_DELIVERY = "non_delivery"      # 未交付
    FRAUD = "fraud"                    # 欺诈
    MISREPRESENTATION = "misrepresentation"  # 描述不符
    OTHER = "other"                    # 其他


# ============================================================================
# 品类关键词映射（从 flash_listing 合并增强）
# ============================================================================

CATEGORY_KEYWORD_MAP: dict = {
    "electronics": ["灯", "电机", "电线", "电池", "电子", "芯片", "LED", "电源",
                    "手机", "电脑", "相机", "耳机", "音箱", "屏幕", "键盘", "鼠标"],
    "machinery": ["轴承", "齿轮", "螺丝", "螺母", "螺栓", "法兰", "联轴器", "减速机",
                  "泵", "阀", "气缸", "液压", "模具", "刀具", "夹具", "机床"],
    "material": ["塑料", "ABS", "PVC", "PE", "PP", "树脂",
                 "钢材", "铜", "铝", "铁", "不锈钢", "铝合金", "铜合金",
                 "化学", "溶剂", "原料", "助剂"],
    "textile": ["布料", "面料", "纱线", "纤维", "纺织", "服装", "成衣"],
    "food": ["食品", "农产品", "粮油", "调料", "干果", "茶叶", "零食"],
    "fashion": ["服饰", "箱包", "鞋", "帽", "首饰", "手表", "眼镜"],
    "home": ["家具", "家电", "厨具", "卫浴", "灯具", "装饰"],
    "vehicles": ["汽车", "电动车", "自行车", "摩托车", "配件", "轮胎"],
    "books": ["图书", "教材", "二手书", "画册", "字帖"],
    "service": ["服务", "维修", "加工", "定制", "咨询", "设计", "翻译", "物流"],
    "digital": ["软件", "源码", "模板", "教程", "素材", "API", "SaaS"],
}
