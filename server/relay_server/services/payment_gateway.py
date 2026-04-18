"""
Payment Gateway Service - 统一支付网关服务
=============================================

功能：
1. 接收微信/支付宝支付回调
2. 根据订单的 node_id 找到对应的中继服务器
3. 异步转发支付通知到节点的回调地址

设计：
- 网关作为统一入口，微信/支付宝回调固定 URL
- 节点可能分布在不同服务器上，网关负责消息转发
- 使用异步任务处理回调，确保高可用
"""

import os
import time
import asyncio
import hashlib
import hmac
import json
from typing import Optional, Dict, Any, Tuple, List
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
import httpx

# ============ 支付平台枚举 ============

class PaymentPlatform(str, Enum):
    """支付平台"""
    WECHAT = "wechat"       # 微信支付
    ALIPAY = "alipay"       # 支付宝
    STRIPE = "stripe"       # Stripe（国际）


class PayStatus(str, Enum):
    """支付状态"""
    PENDING = "pending"     # 待支付
    SUCCESS = "success"     # 成功
    FAILED = "failed"       # 失败
    REFUNDED = "refunded"   # 已退款
    CLOSED = "closed"       # 已关闭


# ============ 支付配置 ============

@dataclass
class WechatPayConfig:
    """微信支付配置"""
    app_id: str = ""
    mch_id: str = ""                    # 商户号
    api_key: str = ""                   # API 密钥
    cert_path: Optional[str] = None      # 证书路径（退款时需要）
    notify_url: str = ""                 # 回调地址


@dataclass
class AlipayConfig:
    """支付宝配置"""
    app_id: str = ""
    private_key: str = ""               # 应用私钥
    alipay_public_key: str = ""         # 支付宝公钥
    notify_url: str = ""                # 回调地址


@dataclass
class PaymentConfig:
    """支付网关配置"""
    data_dir: Path = field(default_factory=lambda: Path.home() / ".hermes-desktop" / "relay_server" / "payment")
    
    # 支付平台配置
    wechat: WechatPayConfig = field(default_factory=WechatPayConfig)
    alipay: AlipayConfig = field(default_factory=AlipayConfig)
    
    # 网关配置
    gateway_url: str = ""               # 网关公网地址
    forward_timeout: int = 30           # 转发超时（秒）
    max_retry: int = 5                  # 最大重试次数
    retry_interval: int = 60            # 重试间隔（秒）


# ============ 支付订单 ============

@dataclass
class PaymentOrder:
    """支付订单"""
    order_id: str
    node_id: str
    user_id: str
    
    amount: float                        # 金额（元）
    currency: str = "CNY"
    subject: str = ""                    # 订单标题
    description: Optional[str] = None   # 订单描述
    
    platform: PaymentPlatform = PaymentPlatform.WECHAT
    status: PayStatus = PayStatus.PENDING
    
    # 支付渠道
    trade_no: Optional[str] = None       # 第三方交易号
    payer_openid: Optional[str] = None   # 支付者 OpenID
    
    # 时间戳
    created_at: int = field(default_factory=lambda: int(time.time()))
    paid_at: Optional[int] = None
    expired_at: Optional[int] = None     # 过期时间
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "node_id": self.node_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "currency": self.currency,
            "subject": self.subject,
            "description": self.description,
            "platform": self.platform.value if isinstance(self.platform, PaymentPlatform) else self.platform,
            "status": self.status.value if isinstance(self.status, PayStatus) else self.status,
            "trade_no": self.trade_no,
            "payer_openid": self.payer_openid,
            "created_at": self.created_at,
            "paid_at": self.paid_at,
            "expired_at": self.expired_at,
            "metadata": self.metadata,
        }


# ============ 回调记录 ============

@dataclass
class CallbackRecord:
    """回调记录"""
    callback_id: str
    order_id: str
    node_id: str
    platform: str
    
    # 回调内容
    request_data: Dict[str, Any]
    response_data: Optional[Dict[str, Any]] = None
    
    # 转发状态
    forward_status: str = "pending"       # pending/success/failed
    forward_count: int = 0
    last_forward_at: Optional[int] = None
    forward_error: Optional[str] = None
    
    # 时间戳
    received_at: int = field(default_factory=lambda: int(time.time()))
    completed_at: Optional[int] = None


# ============ 存储层 ============

class PaymentStorage:
    """支付数据存储"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.orders_file = data_dir / "orders.json"
        self.callbacks_file = data_dir / "callbacks.json"
        self.pending_file = data_dir / "pending_forward.json"
        
        for f in [self.orders_file, self.callbacks_file, self.pending_file]:
            if not f.exists():
                f.write_text("{}", encoding="utf-8")
    
    def _load_json(self, file: Path) -> Dict[str, Any]:
        try:
            return json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    
    def _save_json(self, file: Path, data: Dict[str, Any]):
        file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # ============ 订单操作 ============
    
    def save_order(self, order: PaymentOrder):
        data = self._load_json(self.orders_file)
        data[order.order_id] = order.to_dict()
        self._save_json(self.orders_file, data)
    
    def get_order(self, order_id: str) -> Optional[PaymentOrder]:
        data = self._load_json(self.orders_file)
        if order_id in data:
            return PaymentOrder(**data[order_id])
        return None
    
    def get_orders_by_node(self, node_id: str) -> List[PaymentOrder]:
        data = self._load_json(self.orders_file)
        return [PaymentOrder(**o) for o in data.values() if o.get("node_id") == node_id]
    
    def get_orders_by_user(self, user_id: str) -> List[PaymentOrder]:
        data = self._load_json(self.orders_file)
        return [PaymentOrder(**o) for o in data.values() if o.get("user_id") == user_id]
    
    def update_order_status(self, order_id: str, status: PayStatus, trade_no: Optional[str] = None) -> bool:
        order = self.get_order(order_id)
        if not order:
            return False
        
        order.status = status
        if trade_no:
            order.trade_no = trade_no
        if status == PayStatus.SUCCESS:
            order.paid_at = int(time.time())
        
        self.save_order(order)
        return True
    
    # ============ 回调记录操作 ============
    
    def save_callback(self, record: CallbackRecord):
        data = self._load_json(self.callbacks_file)
        data[record.callback_id] = {
            "callback_id": record.callback_id,
            "order_id": record.order_id,
            "node_id": record.node_id,
            "platform": record.platform,
            "request_data": record.request_data,
            "response_data": record.response_data,
            "forward_status": record.forward_status,
            "forward_count": record.forward_count,
            "last_forward_at": record.last_forward_at,
            "forward_error": record.forward_error,
            "received_at": record.received_at,
            "completed_at": record.completed_at,
        }
        self._save_json(self.callbacks_file, data)
    
    def get_pending_callbacks(self) -> List[CallbackRecord]:
        """获取待转发的回调"""
        data = self._load_json(self.callbacks_file)
        pending = []
        for r in data.values():
            if r.get("forward_status") in ("pending", "failed") and r.get("forward_count", 0) < 5:
                pending.append(CallbackRecord(**r))
        return pending
    
    # ============ 待处理队列 ============
    
    def add_pending_forward(self, order_id: str, node_id: str, callback_data: Dict[str, Any]):
        """添加待转发任务"""
        data = self._load_json(self.pending_file)
        data[order_id] = {
            "order_id": order_id,
            "node_id": node_id,
            "callback_data": callback_data,
            "added_at": int(time.time()),
            "retry_count": 0,
        }
        self._save_json(self.pending_file, data)
    
    def get_pending_forward(self) -> Dict[str, Any]:
        """获取所有待转发任务"""
        return self._load_json(self.pending_file)
    
    def remove_pending_forward(self, order_id: str):
        """移除待转发任务"""
        data = self._load_json(self.pending_file)
        if order_id in data:
            del data[order_id]
            self._save_json(self.pending_file, data)
    
    def update_pending_forward(self, order_id: str, retry_count: int):
        """更新待转发任务"""
        data = self._load_json(self.pending_file)
        if order_id in data:
            data[order_id]["retry_count"] = retry_count
            data[order_id]["last_retry_at"] = int(time.time())
            self._save_json(self.pending_file, data)


# ============ 微信支付实现 ============

class WechatPay:
    """微信支付"""
    
    def __init__(self, config: WechatPayConfig):
        self.config = config
    
    def _generate_sign(self, params: Dict[str, Any]) -> str:
        """生成签名"""
        sorted_params = sorted([(k, v) for k, v in params.items() if k != "sign" and v])
        sign_str = "&".join([f"{k}={v}" for k, v in sorted_params])
        sign_str += f"&key={self.config.api_key}"
        return hashlib.md5(sign_str.encode()).hexdigest().upper()
    
    def _verify_sign(self, params: Dict[str, Any]) -> bool:
        """验证签名"""
        received_sign = params.get("sign", "")
        calculated_sign = self._generate_sign(params)
        return received_sign == calculated_sign
    
    async def unified_order(
        self,
        order_id: str,
        amount: float,
        subject: str,
        notify_url: str,
        openid: Optional[str] = None
    ) -> Tuple[Optional[str], str]:
        """
        统一下单
        
        Returns:
            (prepay_id or pay_url, error_message)
        """
        # 实际对接时，这里调用微信支付 API
        # https://api.mch.weixin.qq.com/pay/unifiedorder
        
        # 模拟返回
        mock_prepay_id = f"wx{invoice_id}" if False else None
        
        return mock_prepay_id, "微信支付接口待对接"
    
    def parse_callback(self, data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        解析回调数据
        
        Returns:
            (is_success, order_id, parsed_data)
        """
        if not self._verify_sign(data):
            return False, "", {}
        
        return True, data.get("out_trade_no", ""), {
            "trade_no": data.get("transaction_id"),
            "trade_status": data.get("trade_state"),
            "total_fee": data.get("total_fee", 0) / 100,  # 分转元
            "paid_at": int(time.time()),
            "openid": data.get("openid"),
        }


# ============ 支付宝实现 ============

class Alipay:
    """支付宝"""
    
    def __init__(self, config: AlipayConfig):
        self.config = config
    
    def _generate_sign(self, params: Dict[str, Any]) -> str:
        """生成签名（RSA2）"""
        # 实际对接时使用 rsa 签名
        # from cryptography.hazmat.primitives import hashes, serialization
        # from cryptography.hazmat.backends import default_backend
        sign_str = json.dumps(params, separators=(',', ':'))
        return hashlib.sha256(sign_str.encode()).hexdigest()
    
    def _verify_sign(self, params: Dict[str, Any], sign: str) -> bool:
        """验证签名"""
        return True  # 简化实现
    
    async def trade_page_pay(
        self,
        order_id: str,
        amount: float,
        subject: str,
        notify_url: str
    ) -> Tuple[Optional[str], str]:
        """
        电脑网站支付
        
        Returns:
            (pay_url, error_message)
        """
        # 实际对接时调用支付宝 API
        # https://openapi.alipay.com/gateway.do
        
        return None, "支付宝接口待对接"
    
    def parse_callback(self, data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        解析回调数据
        
        Returns:
            (is_success, order_id, parsed_data)
        """
        sign = data.get("sign", "")
        if not self._verify_sign(data, sign):
            return False, "", {}
        
        trade_status = data.get("trade_status", "")
        if trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            return False, "", {}
        
        return True, data.get("out_trade_no", ""), {
            "trade_no": data.get("trade_no"),
            "trade_status": trade_status,
            "total_amount": float(data.get("total_amount", 0)),
            "paid_at": int(time.time()),
        }


# ============ 统一支付网关 ============

class UnifiedPaymentGateway:
    """
    统一支付网关
    
    核心功能：
    1. 接收微信/支付宝回调
    2. 验证签名，更新订单状态
    3. 异步转发通知到对应节点的回调地址
    """
    
    def __init__(self, storage: PaymentStorage, config: PaymentConfig):
        self.storage = storage
        self.config = config
        
        # 初始化支付渠道
        self.wechat = WechatPay(config.wechat) if config.wechat.app_id else None
        self.alipay = Alipay(config.alipay) if config.alipay.app_id else None
        
        # 待转发队列
        self._forward_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
    
    @classmethod
    def from_config_file(cls, config_path: Optional[Path] = None) -> "UnifiedPaymentGateway":
        """从配置文件加载"""
        if config_path is None:
            config_path = Path.home() / ".hermes-desktop" / "relay_server" / "payment" / "config.json"
        
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            
            wechat_data = data.get("wechat", {})
            wechat_config = WechatPayConfig(
                app_id=wechat_data.get("app_id", ""),
                mch_id=wechat_data.get("mch_id", ""),
                api_key=wechat_data.get("api_key", ""),
                cert_path=wechat_data.get("cert_path"),
                notify_url=wechat_data.get("notify_url", ""),
            )
            
            alipay_data = data.get("alipay", {})
            alipay_config = AlipayConfig(
                app_id=alipay_data.get("app_id", ""),
                private_key=alipay_data.get("private_key", ""),
                alipay_public_key=alipay_data.get("alipay_public_key", ""),
                notify_url=alipay_data.get("notify_url", ""),
            )
            
            payment_config = PaymentConfig(
                data_dir=config_path.parent,
                wechat=wechat_config,
                alipay=alipay_config,
                gateway_url=data.get("gateway_url", ""),
            )
        else:
            payment_config = PaymentConfig()
        
        storage = PaymentStorage(payment_config.data_dir)
        return cls(storage, payment_config)
    
    async def create_order(
        self,
        order_id: str,
        node_id: str,
        user_id: str,
        amount: float,
        subject: str,
        platform: PaymentPlatform = PaymentPlatform.WECHAT,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expire_minutes: int = 30
    ) -> PaymentOrder:
        """创建支付订单"""
        order = PaymentOrder(
            order_id=order_id,
            node_id=node_id,
            user_id=user_id,
            amount=amount,
            subject=subject,
            description=description,
            platform=platform,
            status=PayStatus.PENDING,
            expired_at=int(time.time()) + expire_minutes * 60,
            metadata=metadata or {},
        )
        self.storage.save_order(order)
        return order
    
    async def get_pay_url(
        self,
        order: PaymentOrder,
        notify_url: str,
        openid: Optional[str] = None
    ) -> Tuple[Optional[str], str]:
        """获取支付链接"""
        if order.platform == PaymentPlatform.WECHAT and self.wechat:
            return await self.wechat.unified_order(
                order_id=order.order_id,
                amount=order.amount,
                subject=order.subject,
                notify_url=notify_url,
                openid=openid,
            )
        elif order.platform == PaymentPlatform.ALIPAY and self.alipay:
            return await self.alipay.trade_page_pay(
                order_id=order.order_id,
                amount=order.amount,
                subject=order.subject,
                notify_url=notify_url,
            )
        
        return None, f"支付平台 {order.platform} 未配置"
    
    async def handle_wechat_callback(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        处理微信支付回调
        
        微信支付回调URL固定，需要网关统一接收后转发
        """
        if not self.wechat:
            return False, "微信支付未配置"
        
        success, order_id, parsed = self.wechat.parse_callback(data)
        
        if not success:
            return False, "签名验证失败"
        
        if not order_id:
            return False, "订单号不存在"
        
        # 更新订单状态
        status = PayStatus.SUCCESS if parsed.get("trade_status") == "SUCCESS" else PayStatus.FAILED
        self.storage.update_order_status(order_id, status, parsed.get("trade_no"))
        
        # 记录回调
        record = CallbackRecord(
            callback_id=f"cb_{int(time.time())}_{order_id}",
            order_id=order_id,
            node_id=self.storage.get_order(order_id).node_id if self.storage.get_order(order_id) else "",
            platform="wechat",
            request_data=data,
            response_data=parsed,
        )
        self.storage.save_callback(record)
        
        # 异步转发给节点
        order = self.storage.get_order(order_id)
        if order:
            await self._forward_to_node(order, "wechat", data)
        
        return True, "处理成功"
    
    async def handle_alipay_callback(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        处理支付宝回调
        """
        if not self.alipay:
            return False, "支付宝未配置"
        
        success, order_id, parsed = self.alipay.parse_callback(data)
        
        if not success:
            return False, "签名验证失败"
        
        if not order_id:
            return False, "订单号不存在"
        
        # 更新订单状态
        status = PayStatus.SUCCESS if "SUCCESS" in parsed.get("trade_status", "") else PayStatus.FAILED
        self.storage.update_order_status(order_id, status, parsed.get("trade_no"))
        
        # 记录回调
        record = CallbackRecord(
            callback_id=f"cb_{int(time.time())}_{order_id}",
            order_id=order_id,
            node_id=self.storage.get_order(order_id).node_id if self.storage.get_order(order_id) else "",
            platform="alipay",
            request_data=data,
            response_data=parsed,
        )
        self.storage.save_callback(record)
        
        # 异步转发给节点
        order = self.storage.get_order(order_id)
        if order:
            await self._forward_to_node(order, "alipay", data)
        
        return True, "处理成功"
    
    async def _forward_to_node(
        self,
        order: PaymentOrder,
        platform: str,
        callback_data: Dict[str, Any]
    ):
        """
        转发支付通知到节点的回调地址
        
        关键：节点可能分布在不同服务器，节点注册时提供 relay_url
        """
        # 获取节点的 relay_url
        # 这里需要调用 NodeService 获取
        from server.relay_server.services.user_auth_service import get_node_service
        
        node_service = get_node_service()
        node = node_service.storage.get_node_by_id(order.node_id)
        
        if not node or not node.relay_url:
            # 节点未注册或无 relay_url，加入待转发队列
            self.storage.add_pending_forward(order.order_id, order.node_id, callback_data)
            return
        
        # 构建回调 URL
        callback_url = f"{node.relay_url.rstrip('/')}/api/payment/callback"
        
        # 异步转发
        try:
            async with httpx.AsyncClient(timeout=self.config.forward_timeout) as client:
                response = await client.post(
                    callback_url,
                    json={
                        "order_id": order.order_id,
                        "node_id": order.node_id,
                        "platform": platform,
                        "status": order.status.value,
                        "trade_no": order.trade_no,
                        "amount": order.amount,
                        "paid_at": order.paid_at,
                        "metadata": order.metadata,
                    }
                )
                
                if response.status_code == 200:
                    # 转发成功
                    self.storage.remove_pending_forward(order.order_id)
                    return
        except Exception as e:
            pass
        
        # 转发失败，计数
        pending = self.storage.get_pending_forward()
        if order.order_id in pending:
            retry_count = pending[order.order_id].get("retry_count", 0) + 1
            if retry_count >= self.config.max_retry:
                # 达到最大重试次数，放弃
                pass
            else:
                self.storage.update_pending_forward(order.order_id, retry_count)
    
    async def retry_pending_forwards(self):
        """重试待转发的回调"""
        pending = self.storage.get_pending_forward()
        
        for order_id, item in pending.items():
            retry_count = item.get("retry_count", 0)
            if retry_count >= self.config.max_retry:
                continue
            
            # 检查是否在重试间隔内
            last_retry = item.get("last_retry_at", 0)
            if time.time() - last_retry < self.config.retry_interval:
                continue
            
            # 重试转发
            order = self.storage.get_order(order_id)
            if order:
                await self._forward_to_node(order, "wechat", item.get("callback_data", {}))
    
    def get_order(self, order_id: str) -> Optional[PaymentOrder]:
        """获取订单"""
        return self.storage.get_order(order_id)
    
    def get_node_orders(self, node_id: str) -> List[PaymentOrder]:
        """获取节点的所有订单"""
        return self.storage.get_orders_by_node(node_id)
    
    def get_user_orders(self, user_id: str) -> List[PaymentOrder]:
        """获取用户的所有订单"""
        return self.storage.get_orders_by_user(user_id)


# ============ 单例 ============

_payment_gateway: Optional[UnifiedPaymentGateway] = None


def get_payment_gateway() -> UnifiedPaymentGateway:
    global _payment_gateway
    if _payment_gateway is None:
        _payment_gateway = UnifiedPaymentGateway.from_config_file()
    return _payment_gateway
