"""
P2P 去中心化电商 - 社会物流追踪
Social Logistics Tracker

集成快递鸟/快递100聚合API，实现物流轨迹追踪。
Broker做匿名中转，不存储真实地址。

流程:
1. 卖家发货 → 填快递单号 → 加密发给Broker
2. Broker转发给买家 (不落盘)
3. 买家查询轨迹 → Broker调用快递API → 推送结果
4. 签收状态哈希存证 → 触发自动解冻
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
import time
import uuid
import hashlib
import json

logger = logging.getLogger(__name__)


class LogisticsStatus(Enum):
    """物流状态"""
    PENDING = "pending"           # 待发货
    SHIPPED = "shipped"          # 已发货
    IN_TRANSIT = "in_transit"    # 运输中
    OUT_FOR_DELIVERY = "out_for_delivery"  # 派送中
    DELIVERED = "delivered"      # 已签收
    EXCEPTION = "exception"       # 异常
    RETURNED = "returned"         # 退回


class CarrierType(Enum):
    """快递公司类型"""
    # 主流快递
    SF = "sf"                     # 顺丰速运
    YTO = "yto"                   # 圆通速递
    ZTO = "zto"                   # 中通快递
    STO = "sto"                   # 申通速递
    YUNDA = "yunda"               # 韵达速递
    JD = "jd"                     # 京东物流
    EMS = "ems"                   # 中国邮政EMS
    GT = "gt"                     # 极兔速递

    # 其他
    OTHER = "other"


@dataclass
class LogisticsRecord:
    """物流记录"""
    # 基础信息
    order_id: str = ""
    listing_id: str = ""

    # 快递信息
    carrier: CarrierType = CarrierType.OTHER
    carrier_name: str = ""
    tracking_number: str = ""

    # 发货人信息 (加密,不存储明文)
    sender_encrypted: str = ""  # 加密的发送方信息
    sender_hash: str = ""      # 发送方信息哈希 (用于验证)

    # 收货人信息 (加密)
    receiver_encrypted: str = ""
    receiver_hash: str = ""

    # 状态
    status: LogisticsStatus = LogisticsStatus.PENDING

    # 轨迹
    traces: List[Dict[str, Any]] = field(default_factory=list)

    # 时间戳
    created_at: float = 0
    shipped_at: float = 0
    delivered_at: float = 0
    last_updated: float = 0

    # Broker转发标识
    broker_relay_id: str = ""  # Broker转发用的ID

    def compute_hash(self) -> str:
        """计算物流记录哈希"""
        content = f"{self.order_id}|{self.carrier.value}|{self.tracking_number}|{self.sender_hash}|{self.receiver_hash}"
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "listing_id": self.listing_id,
            "carrier": self.carrier.value,
            "carrier_name": self.carrier_name,
            "tracking_number": self.tracking_number,
            "status": self.status.value,
            "traces": self.traces,
            "created_at": self.created_at,
            "shipped_at": self.shipped_at,
            "delivered_at": self.delivered_at,
            "last_updated": self.last_updated,
        }

    def to_broker_relay(self) -> Dict[str, Any]:
        """生成Broker转发数据 (不含敏感信息)"""
        return {
            "broker_relay_id": self.broker_relay_id,
            "order_id": self.order_id,
            "carrier": self.carrier.value,
            "tracking_number": self.tracking_number[-4:],  # 只传后4位
            "status": self.status.value,
        }


@dataclass
class LogisticsTrace:
    """物流轨迹点"""
    status: str = ""
    description: str = ""
    location: str = ""
    timestamp: float = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "description": self.description,
            "location": self.location,
            "timestamp": self.timestamp,
        }


class LogisticsTracker:
    """
    社会物流追踪器

    功能:
    1. 快递公司匹配
    2. 轨迹查询 (快递鸟/快递100)
    3. Broker匿名转发
    4. 签收存证
    """

    def __init__(
        self,
        kuaidi100_api: Optional[str] = None,
        kuaidi100_customer: Optional[str] = None,
    ):
        # API配置
        self.kuaidi100_api = kuaidi100_api
        self.kuaidi100_customer = kuaidi100_customer

        # 物流记录
        self._records: Dict[str, LogisticsRecord] = {}  # order_id -> record
        self._by_tracking: Dict[str, str] = {}  # tracking_number -> order_id

        # Broker转发缓存 (用于匿名推送)
        self._relay_cache: Dict[str, str] = {}  # broker_relay_id -> order_id

        # 回调
        self._on_status_changed: List[Callable] = []
        self._on_delivered: List[Callable] = []

        logger.info("[LogisticsTracker] Initialized")

    def _get_carrier_code(self, carrier: CarrierType) -> str:
        """获取快递公司代码"""
        codes = {
            CarrierType.SF: "shunfeng",
            CarrierType.YTO: "yuantong",
            CarrierType.ZTO: "zhongtong",
            CarrierType.STO: "shentong",
            CarrierType.YUNDA: "yunda",
            CarrierType.JD: "jd",
            CarrierType.EMS: "ems",
            CarrierType.GT: "jtexpress",
        }
        return codes.get(carrier, "other")

    def _parse_carrier(self, carrier_name: str) -> CarrierType:
        """从名称解析快递公司"""
        name_lower = carrier_name.lower()

        if "顺丰" in name_lower or "sf" in name_lower:
            return CarrierType.SF
        elif "圆通" in name_lower or "yto" in name_lower:
            return CarrierType.YTO
        elif "中通" in name_lower or "zto" in name_lower:
            return CarrierType.ZTO
        elif "申通" in name_lower or "sto" in name_lower:
            return CarrierType.STO
        elif "韵达" in name_lower or "yunda" in name_lower:
            return CarrierType.YUNDA
        elif "京东" in name_lower or "jd" in name_lower:
            return CarrierType.JD
        elif "邮政" in name_lower or "ems" in name_lower:
            return CarrierType.EMS
        elif "极兔" in name_lower or "jtex" in name_lower:
            return CarrierType.GT

        return CarrierType.OTHER

    # ==================== 发货 ====================

    async def create_shipment(
        self,
        order_id: str,
        listing_id: str,
        carrier_name: str,
        tracking_number: str,
        sender_info: Dict[str, Any],
        receiver_info: Dict[str, Any],
    ) -> LogisticsRecord:
        """创建发货记录"""
        carrier = self._parse_carrier(carrier_name)

        # 加密敏感信息 (不存储明文)
        sender_json = json.dumps(sender_info, sort_keys=True)
        receiver_json = json.dumps(receiver_info, sort_keys=True)

        record = LogisticsRecord(
            order_id=order_id,
            listing_id=listing_id,
            carrier=carrier,
            carrier_name=carrier_name,
            tracking_number=tracking_number,
            sender_encrypted=self._encrypt(sender_json),
            sender_hash=hashlib.sha256(sender_json.encode()).hexdigest(),
            receiver_encrypted=self._encrypt(receiver_json),
            receiver_hash=hashlib.sha256(receiver_json.encode()).hexdigest(),
            status=LogisticsStatus.SHIPPED,
            created_at=time.time(),
            shipped_at=time.time(),
            last_updated=time.time(),
            broker_relay_id=str(uuid.uuid4())[:12],
        )

        self._records[order_id] = record
        self._by_tracking[tracking_number] = order_id
        self._relay_cache[record.broker_relay_id] = order_id

        logger.info(f"[LogisticsTracker] Created shipment for order {order_id}: {carrier_name} {tracking_number}")

        return record

    async def relay_shipment_to_broker(self, order_id: str, broker) -> Optional[Dict[str, Any]]:
        """通过Broker匿名转发发货信息"""
        record = self._records.get(order_id)
        if not record:
            return None

        # 只发送用于追踪的最小信息
        relay_data = record.to_broker_relay()

        logger.info(f"[LogisticsTracker] Relayed shipment to broker: {record.broker_relay_id}")

        return relay_data

    # ==================== 轨迹查询 ====================

    async def query_tracking(self, order_id: str) -> Optional[LogisticsRecord]:
        """查询物流轨迹"""
        record = self._records.get(order_id)
        if not record:
            return None

        try:
            # 调用快递100 API
            traces = await self._query_kuaidi100(
                carrier=record.carrier,
                tracking_number=record.tracking_number,
            )

            if traces:
                record.traces = traces
                record.last_updated = time.time()

                # 更新状态
                self._update_status_from_traces(record)

                logger.info(f"[LogisticsTracker] Updated tracking for order {order_id}: {len(traces)} traces")

        except Exception as e:
            logger.error(f"[LogisticsTracker] Failed to query tracking: {e}")

        return record

    async def _query_kuaidi100(
        self,
        carrier: CarrierType,
        tracking_number: str,
    ) -> List[Dict[str, Any]]:
        """调用快递100 API查询"""
        if not self.kuaidi100_api:
            # 无API时的模拟
            return self._mock_traces(carrier, tracking_number)

        try:
            import aiohttp

            url = "https://api.kuaidi100.com/api"
            params = {
                "id": self.kuaidi100_api,
                "com": self._get_carrier_code(carrier),
                "nu": tracking_number,
                "show": "0",  # 0: JSON格式
                "muti": "1",  # 返回多态
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return self._parse_kuaidi100_response(data)

        except Exception as e:
            logger.error(f"[LogisticsTracker] Kuaidi100 API error: {e}")

        return []

    def _parse_kuaidi100_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析快递100响应"""
        traces = []

        if data.get("status") == "200":
            for item in data.get("data", []):
                trace = LogisticsTrace(
                    status=item.get("status", ""),
                    description=item.get("context", ""),
                    location=item.get("location", ""),
                    timestamp=self._parse_time(item.get("ftime", "")),
                )
                traces.append(trace.to_dict())

        return traces

    def _parse_time(self, time_str: str) -> float:
        """解析时间字符串"""
        if not time_str:
            return time.time()

        # 尝试解析常见格式
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                from datetime import datetime
                dt = datetime.strptime(time_str, fmt)
                return dt.timestamp()
            except:
                continue

        return time.time()

    def _mock_traces(self, carrier: CarrierType, tracking_number: str) -> List[Dict[str, Any]]:
        """模拟轨迹 (无API时)"""
        now = time.time()

        return [
            {
                "status": "已发货",
                "description": f"包裹已从【{carrier.name}】发出",
                "location": "发货地",
                "timestamp": now - 86400,
            },
            {
                "status": "运输中",
                "description": "包裹正在运输途中",
                "location": "中转中心",
                "timestamp": now - 43200,
            },
            {
                "status": "派送中",
                "description": "包裹正在派送中，请保持电话畅通",
                "location": "收件地",
                "timestamp": now - 3600,
            },
        ]

    async def _update_status_from_traces(self, record: LogisticsRecord) -> None:
        """根据轨迹更新状态"""
        if not record.traces:
            return

        latest = record.traces[-1].get("status", "")

        old_status = record.status

        if "签收" in latest or "已签收" in latest:
            record.status = LogisticsStatus.DELIVERED
            record.delivered_at = time.time()

            # 触发送达回调
            for cb in self._on_delivered:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(record.order_id, record)
                    else:
                        cb(record.order_id, record)
                except Exception as e:
                    logger.error(f"[LogisticsTracker] Delivered callback error: {e}")

        elif "派送" in latest:
            record.status = LogisticsStatus.OUT_FOR_DELIVERY

        elif "在途" in latest or "运输" in latest:
            record.status = LogisticsStatus.IN_TRANSIT

        elif "异常" in latest or "退回" in latest:
            record.status = LogisticsStatus.EXCEPTION

        if old_status != record.status:
            # 触发状态变化回调
            for cb in self._on_status_changed:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(record.order_id, old_status, record.status)
                    else:
                        cb(record.order_id, old_status, record.status)
                except Exception as e:
                    logger.error(f"[LogisticsTracker] Status changed callback error: {e}")

    # ==================== Broker转发 ====================

    async def push_to_peers(
        self,
        order_id: str,
        seller_id: str,
        buyer_id: str,
        broker,
    ) -> bool:
        """
        通过Broker匿名中转推送物流信息给买卖双方

        Broker不存储真实地址，只做消息转发
        """
        record = self._records.get(order_id)
        if not record:
            return False

        # 构建匿名推送消息
        anonymous_msg = {
            "type": "logistics_update",
            "broker_relay_id": record.broker_relay_id,
            "order_id": order_id,
            "carrier": record.carrier.value,
            "tracking_number_masked": f"****{record.tracking_number[-4:]}",
            "status": record.status.value,
            "last_trace": record.traces[-1] if record.traces else None,
            "timestamp": time.time(),
        }

        # 通过Broker推送给双方
        if broker:
            try:
                await broker.forward_to_peer(seller_id, anonymous_msg)
                await broker.forward_to_peer(buyer_id, anonymous_msg)
            except Exception as e:
                logger.error(f"[LogisticsTracker] Failed to push to peers: {e}")
                return False

        return True

    # ==================== 签收存证 ====================

    def create_delivery_proof(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        创建签收证明 (用于自动解冻)

        返回包含哈希的签收证据
        """
        record = self._records.get(order_id)
        if not record or record.status != LogisticsStatus.DELIVERED:
            return None

        proof = {
            "order_id": order_id,
            "delivery_hash": record.compute_hash(),
            "delivery_proof": {
                "carrier": record.carrier.value,
                "tracking_number": record.tracking_number,
                "delivered_at": record.delivered_at,
                "last_trace": record.traces[-1] if record.traces else None,
            },
            "signer_hash": hashlib.sha256(
                f"{order_id}|{record.delivered_at}|verified".encode()
            ).hexdigest(),
            "timestamp": time.time(),
        }

        logger.info(f"[LogisticsTracker] Created delivery proof for order {order_id}")

        return proof

    # ==================== 加密/解密 ====================

    def _encrypt(self, data: str) -> str:
        """简单加密 (实际应使用真正的加密)"""
        # 这里应该使用AES或其他对称加密
        return hashlib.sha256(data.encode()).hexdigest()

    def _decrypt(self, encrypted: str) -> str:
        """简单解密"""
        # 对称加密才能解密
        return encrypted

    # ==================== 查询 ====================

    def get_record(self, order_id: str) -> Optional[LogisticsRecord]:
        """获取物流记录"""
        return self._records.get(order_id)

    def get_record_by_tracking(self, tracking_number: str) -> Optional[LogisticsRecord]:
        """通过单号获取物流记录"""
        order_id = self._by_tracking.get(tracking_number)
        if order_id:
            return self._records.get(order_id)
        return None

    def get_records_by_status(self, status: LogisticsStatus) -> List[LogisticsRecord]:
        """获取指定状态的物流记录"""
        return [r for r in self._records.values() if r.status == status]

    # ==================== 回调 ====================

    def on_status_changed(self, callback: Callable) -> None:
        """监听状态变化"""
        self._on_status_changed.append(callback)

    def on_delivered(self, callback: Callable) -> None:
        """监听送达"""
        self._on_delivered.append(callback)

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        records = list(self._records.values())

        return {
            "total_records": len(records),
            "by_status": {
                status.value: sum(1 for r in records if r.status == status)
                for status in LogisticsStatus
            },
            "delivered_today": sum(
                1 for r in records
                if r.status == LogisticsStatus.DELIVERED
                and r.delivered_at > time.time() - 86400
            ),
        }


# ==================== 全局实例 ====================

_logistics_tracker: Optional[LogisticsTracker] = None


def get_logistics_tracker() -> LogisticsTracker:
    """获取物流追踪器"""
    global _logistics_tracker
    if _logistics_tracker is None:
        _logistics_tracker = LogisticsTracker()
    return _logistics_tracker
