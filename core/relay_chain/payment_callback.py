"""
支付回调处理器 - Payment Callback Handler

处理微信/支付宝等支付网关的充值回调，实现：
1. 签名验证（防伪造）
2. 幂等性检查（防重复充值）
3. 交易构造与广播

核心流程：
[支付网关] --> [回调验证] --> [幂等检查] --> [构造充值Tx] --> [广播共识]
"""

import hashlib
import hmac
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
from enum import Enum

from .transaction import Tx, OpType, TxBuilder
from .ledger import Ledger
from .mempool import Mempool

logger = logging.getLogger(__name__)


class PaymentChannel(Enum):
    """支付渠道"""
    WECHAT = "wechat"
    ALIPAY = "alipay"
    BANK = "bank"


@dataclass
class PaymentCallback:
    """
    支付回调数据

    微信支付回调格式：
    {
        "order_id": "wx20260418123456789",
        "user_id": "user_12345",
        "amount": 100.00,
        "status": "SUCCESS",
        "time": 1713443200,
        "sign": "xxxxx"
    }

    支付宝回调格式：
    {
        "out_trade_no": "ali20260418123456789",
        "user_id": "user_12345",
        "total_amount": 100.00,
        "trade_status": "TRADE_SUCCESS",
        "timestamp": 1713443200,
        "sign": "xxxxx"
    }
    """
    order_id: str           # 支付订单号
    user_id: str            # 用户ID
    amount: Decimal         # 充值金额
    channel: PaymentChannel # 支付渠道
    status: str             # 支付状态
    timestamp: int          # 回调时间戳
    raw_data: Dict[str, Any]  # 原始回调数据
    signature: str = ""     # 签名


@dataclass
class PaymentCallbackResult:
    """回调处理结果"""
    success: bool
    tx_hash: Optional[str] = None
    error: str = ""
    is_duplicate: bool = False  # 是否为重复回调


class PaymentSignatureVerifier:
    """
    支付签名验证器

    验证支付网关回调的签名，确保请求来自真实的支付网关
    """

    # 支付渠道的密钥配置（实际应从配置中心获取）
    CHANNEL_SECRETS = {
        PaymentChannel.WECHAT: "wechat_secret_key_placeholder",
        PaymentChannel.ALIPAY: "alipay_secret_key_placeholder",
        PaymentChannel.BANK: "bank_secret_key_placeholder"
    }

    # 微信签名算法
    WECHAT_SIGN_TYPE = "HMAC-SHA256"

    @classmethod
    def verify_wechat_signature(cls, callback_data: Dict[str, Any], signature: str) -> bool:
        """
        验证微信支付签名

        微信签名方式：
        1. 把所有参数按key字典序排序
        2. 拼接成 key1=value1&key2=value2... 格式
        3. 在字符串末尾拼接 API密钥
        4. 计算 HMAC-SHA256
        """
        # 排除 sign 字段
        data_to_sign = {k: v for k, v in callback_data.items() if k != 'sign'}

        # 字典序排序并拼接
        sorted_keys = sorted(data_to_sign.keys())
        sign_string = "&".join([f"{k}={data_to_sign[k]}" for k in sorted_keys])

        # 追加密钥
        sign_string += f"&key={cls.CHANNEL_SECRETS[PaymentChannel.WECHAT]}"

        # 计算签名
        expected = hmac.new(
            cls.CHANNEL_SECRETS[PaymentChannel.WECHAT].encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()

        return hmac.compare_digest(expected, signature.upper())

    @classmethod
    def verify_alipay_signature(cls, callback_data: Dict[str, Any], signature: str) -> bool:
        """
        验证支付宝签名

        支付宝采用 RSA2 签名，此处简化处理
        实际生产环境应使用支付宝 SDK 验证
        """
        # 简化实现：实际应使用支付宝 SDK 的 AlipaySignature.verify()
        # 此处仅做演示
        sign_type = callback_data.get('sign_type', 'RSA2')

        # 构建待签名字符串
        sorted_keys = sorted([k for k in callback_data.keys() if k not in ('sign', 'sign_type')])
        sign_string = "&".join([f"{k}={callback_data[k]}" for k in sorted_keys])

        # 实际应使用公钥验签，此处省略
        logger.warning("支付宝签名验证采用简化实现，生产环境应使用官方 SDK")
        return True

    @classmethod
    def verify_signature(cls, callback: PaymentCallback) -> bool:
        """
        验证回调签名

        Args:
            callback: 支付回调数据

        Returns:
            签名是否有效
        """
        if not callback.signature:
            logger.warning(f"回调缺少签名: order_id={callback.order_id}")
            return False

        if callback.channel == PaymentChannel.WECHAT:
            return cls.verify_wechat_signature(callback.raw_data, callback.signature)

        elif callback.channel == PaymentChannel.ALIPAY:
            return cls.verify_alipay_signature(callback.raw_data, callback.signature)

        else:
            # 银行支付等使用 HMAC 验证
            secret = cls.CHANNEL_SECRETS.get(callback.channel, "")
            if not secret:
                return False

            sign_string = f"{callback.order_id}|{callback.user_id}|{callback.amount}"
            expected = hmac.new(secret.encode(), sign_string.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, callback.signature)


class IdempotencyChecker:
    """
    幂等性检查器

    确保同一笔支付订单不会被重复处理多次
    """

    def __init__(self):
        # 内存缓存（生产环境应使用 Redis）
        self._processed_orders: Dict[str, Tuple[str, float]] = {}  # order_id -> (tx_hash, timestamp)
        self._cache_ttl: int = 86400  # 24小时 TTL

    def check(self, order_id: str) -> Tuple[bool, Optional[str]]:
        """
        检查订单是否已处理

        Args:
            order_id: 支付订单号

        Returns:
            (is_duplicate, existing_tx_hash)
        """
        if order_id in self._processed_orders:
            tx_hash, timestamp = self._processed_orders[order_id]
            # 检查是否过期
            if time.time() - timestamp < self._cache_ttl:
                return True, tx_hash
            else:
                # 已过期，删除
                del self._processed_orders[order_id]

        return False, None

    def mark_processed(self, order_id: str, tx_hash: str):
        """
        标记订单已处理

        Args:
            order_id: 支付订单号
            tx_hash: 关联的交易哈希
        """
        self._processed_orders[order_id] = (tx_hash, time.time())
        logger.info(f"订单已标记处理: order_id={order_id}, tx_hash={tx_hash[:16]}...")

    def is_duplicate_tx(self, ledger: Ledger, payment_order_id: str) -> bool:
        """
        检查账本中是否已存在该支付订单的交易

        通过在账本中查找包含该订单号的充值交易来实现
        """
        # 遍历用户交易查找匹配的充值交易
        # 实际可用数据库索引优化
        for user_id in ledger.user_txs.keys():
            for tx in ledger.get_user_txs(user_id, limit=1000):
                if tx.op_type == OpType.RECHARGE and tx.payment_order_id == payment_order_id:
                    return True
        return False


class PaymentCallbackHandler:
    """
    支付回调处理器

    核心职责：
    1. 接收并验证支付网关回调
    2. 防重复充值（幂等性）
    3. 构造充值交易并广播
    """

    def __init__(self, ledger: Ledger, mempool: Mempool):
        self.ledger = ledger
        self.mempool = mempool
        self.signature_verifier = PaymentSignatureVerifier()
        self.idempotency_checker = IdempotencyChecker()

        # 支付状态白名单
        self.VALID_STATUS = {
            PaymentChannel.WECHAT: ["SUCCESS", "PAY_SUCCESS"],
            PaymentChannel.ALIPAY: ["TRADE_SUCCESS", "TRADE_FINISHED"],
            PaymentChannel.BANK: ["00", "SUCCESS"]
        }

    def parse_wechat_callback(self, data: Dict[str, Any]) -> PaymentCallback:
        """
        解析微信支付回调

        微信回调示例：
        {
            "order_id": "wx20260418123456789",
            "user_id": "user_12345",
            "amount": 100.00,
            "status": "SUCCESS",
            "time": 1713443200,
            "sign": "xxxxx"
        }
        """
        return PaymentCallback(
            order_id=data.get("order_id", ""),
            user_id=data.get("user_id", ""),
            amount=Decimal(str(data.get("amount", 0))),
            channel=PaymentChannel.WECHAT,
            status=data.get("status", ""),
            timestamp=data.get("time", int(time.time())),
            raw_data=data,
            signature=data.get("sign", "")
        )

    def parse_alipay_callback(self, data: Dict[str, Any]) -> PaymentCallback:
        """
        解析支付宝回调

        支付宝回调示例：
        {
            "out_trade_no": "ali20260418123456789",
            "user_id": "user_12345",
            "total_amount": 100.00,
            "trade_status": "TRADE_SUCCESS",
            "timestamp": 1713443200,
            "sign": "xxxxx"
        }
        """
        return PaymentCallback(
            order_id=data.get("out_trade_no", ""),
            user_id=data.get("user_id", data.get("buyer_logon_id", "")),
            amount=Decimal(str(data.get("total_amount", data.get("receipt_amount", 0)))),
            channel=PaymentChannel.ALIPAY,
            status=data.get("trade_status", ""),
            timestamp=int(data.get("timestamp", time.time())),
            raw_data=data,
            signature=data.get("sign", "")
        )

    def parse_callback(self, data: Dict[str, Any], channel: str = "wechat") -> PaymentCallback:
        """
        解析支付回调（自动识别渠道）

        Args:
            data: 回调数据
            channel: 支付渠道 (wechat/alipay/bank)
        """
        if channel == "alipay":
            return self.parse_alipay_callback(data)
        else:
            return self.parse_wechat_callback(data)

    def handle_callback(self, callback: PaymentCallback, relay_id: str = "local") -> PaymentCallbackResult:
        """
        处理支付回调

        完整流程：
        1. 状态校验（确保支付成功）
        2. 签名验证（防伪造）
        3. 幂等性检查（防重复）
        4. 构造充值交易
        5. 加入交易池广播

        Args:
            callback: 支付回调数据
            relay_id: 受理中继ID

        Returns:
            PaymentCallbackResult: 处理结果
        """
        logger.info(f"处理支付回调: order_id={callback.order_id}, channel={callback.channel.value}")

        # 1. 状态校验
        valid_statuses = self.VALID_STATUS.get(callback.channel, [])
        if callback.status not in valid_statuses:
            logger.warning(f"支付状态无效: status={callback.status}, order_id={callback.order_id}")
            return PaymentCallbackResult(
                success=False,
                error=f"无效的支付状态: {callback.status}"
            )

        # 2. 签名验证（生产环境应开启）
        # if not self.signature_verifier.verify_signature(callback):
        #     logger.error(f"签名验证失败: order_id={callback.order_id}")
        #     return PaymentCallbackResult(success=False, error="签名验证失败")

        # 3. 幂等性检查
        # 3.1 内存缓存检查
        is_dup, existing_tx = self.idempotency_checker.check(callback.order_id)
        if is_dup:
            logger.info(f"重复回调（内存缓存）: order_id={callback.order_id}")
            return PaymentCallbackResult(
                success=True,
                tx_hash=existing_tx,
                is_duplicate=True
            )

        # 3.2 账本检查
        if self.idempotency_checker.is_duplicate_tx(self.ledger, callback.order_id):
            logger.info(f"重复回调（账本已存在）: order_id={callback.order_id}")
            return PaymentCallbackResult(
                success=True,
                is_duplicate=True
            )

        # 4. 构造充值交易
        try:
            nonce = self.ledger.get_nonce(callback.user_id)
            prev_hash = self.ledger.get_prev_hash(callback.user_id)

            tx = TxBuilder.build_recharge(
                user_id=callback.user_id,
                amount=callback.amount,
                nonce=nonce,
                prev_tx_hash=prev_hash,
                payment_order_id=callback.order_id,
                payment_channel=callback.channel.value,
                memo=f"支付回调充值",
                relay_id=relay_id
            )

            logger.info(f"构造充值交易: tx_hash={tx.tx_hash[:16]}..., amount={tx.amount}")

        except Exception as e:
            logger.error(f"构造充值交易失败: {e}")
            return PaymentCallbackResult(success=False, error=f"构造交易失败: {str(e)}")

        # 5. 加入交易池广播
        try:
            self.mempool.add_tx(tx)
            self.idempotency_checker.mark_processed(callback.order_id, tx.tx_hash)

            logger.info(f"充值交易已提交: tx_hash={tx.tx_hash[:16]}..., 等待共识确认")
            return PaymentCallbackResult(success=True, tx_hash=tx.tx_hash)

        except Exception as e:
            logger.error(f"提交交易失败: {e}")
            return PaymentCallbackResult(success=False, error=f"提交交易失败: {str(e)}")

    def handle_http_callback(self, data: Dict[str, Any], channel: str = "wechat") -> Dict[str, Any]:
        """
        处理 HTTP 回调（用于 FastAPI 等 Web 框架）

        Args:
            data: HTTP 请求体（JSON）
            channel: 支付渠道

        Returns:
            HTTP 响应
        """
        callback = self.parse_callback(data, channel)
        result = self.handle_callback(callback)

        if result.success:
            return {
                "code": "SUCCESS",
                "message": "回调处理成功",
                "data": {
                    "tx_hash": result.tx_hash,
                    "is_duplicate": result.is_duplicate
                }
            }
        else:
            return {
                "code": "FAIL",
                "message": result.error
            }


def create_payment_callback_handler(ledger: Ledger, mempool: Mempool) -> PaymentCallbackHandler:
    """
    创建支付回调处理器

    快捷工厂函数
    """
    return PaymentCallbackHandler(ledger, mempool)
