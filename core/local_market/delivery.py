# -*- coding: utf-8 -*-
"""
交付系统模块
============

交付方式：
- 自提模式：买家到指定地点自提
- 节点配送：顺路节点有偿代送
- 安全交付点：便利店、驿站作为中转
"""

import uuid
import time
import hashlib
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable


class DeliveryType(Enum):
    """交付类型"""
    PICKUP = "pickup"                      # 自提
    DELIVERY = "delivery"                  # 送货上门
    SAFE_POINT = "safe_point"              # 安全交付点


class DeliveryStatus(Enum):
    """交付状态"""
    PENDING = "pending"                    # 待交付
    ARRANGED = "arranged"                 # 已安排
    IN_TRANSIT = "in_transit"             # 运输中
    ARRIVED = "arrived"                    # 已到达
    COMPLETED = "completed"                # 已完成
    FAILED = "failed"                      # 交付失败
    CANCELLED = "cancelled"               # 已取消


@dataclass
class DeliveryRoute:
    """交付路线"""
    route_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    delivery_type: DeliveryType = DeliveryType.PICKUP

    # 起点和终点
    pickup_location: Dict = field(default_factory=dict)  # {"lat": 39.9, "lon": 116.4, "address": "..."}
    dropoff_location: Dict = field(default_factory=dict)

    # 路径点
    waypoints: List[Dict] = field(default_factory=list)

    # 距离和时间
    total_distance_km: float = 0.0
    estimated_time_minutes: int = 0

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['delivery_type'] = self.delivery_type.value
        return data


@dataclass
class DeliveryTask:
    """交付任务"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    transaction_id: str = ""

    # 交付信息
    delivery_type: DeliveryType = DeliveryType.PICKUP
    status: DeliveryStatus = DeliveryStatus.PENDING

    # 参与方
    sender_id: str = ""                    # 发送方（卖家）
    receiver_id: str = ""                 # 接收方（买家）
    courier_id: Optional[str] = None       # 配送员ID（可为节点）

    # 货物信息
    product_id: str = ""
    product_snapshot: Dict = field(default_factory=dict)
    package_description: str = ""         # 包裹描述
    package_weight_kg: float = 0.0         # 重量

    # 位置
    pickup_address: str = ""
    pickup_location: Dict = field(default_factory=dict)
    dropoff_address: str = ""
    dropoff_location: Dict = field(default_factory=dict)

    # 路线
    route: Optional[DeliveryRoute] = None

    # 验证码
    pickup_code: str = ""                  # 取货验证码
    delivery_code: str = ""                # 交付验证码

    # 时间
    scheduled_pickup_time: float = 0
    scheduled_delivery_time: float = 0
    actual_pickup_time: float = 0
    actual_delivery_time: float = 0

    # 费用
    delivery_fee: float = 0.0              # 配送费
    insurance_fee: float = 0.0            # 保险费

    # 状态记录
    status_history: List[Dict] = field(default_factory=list)

    # 创建时间
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['delivery_type'] = self.delivery_type.value
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'DeliveryTask':
        data = data.copy()
        data['delivery_type'] = DeliveryType(data.get('delivery_type', 'pickup'))
        data['status'] = DeliveryStatus(data.get('status', 'pending'))
        return cls(**data)

    def update_timestamp(self):
        self.updated_at = time.time()

    def add_status_history(self, status: DeliveryStatus, note: str = ""):
        """添加状态历史"""
        self.status_history.append({
            "status": status.value,
            "timestamp": time.time(),
            "note": note,
        })
        self.update_timestamp()

    def generate_codes(self):
        """生成验证码"""
        self.pickup_code = hashlib.sha256(
            f"{self.task_id}:pickup:{time.time()}".encode()
        ).hexdigest()[:6].upper()
        self.delivery_code = hashlib.sha256(
            f"{self.task_id}:delivery:{time.time()}".encode()
        ).hexdigest()[:6].upper()
        return self.pickup_code, self.delivery_code

    def verify_pickup_code(self, code: str) -> bool:
        """验证取货码"""
        return code.upper() == self.pickup_code.upper()

    def verify_delivery_code(self, code: str) -> bool:
        """验证交付码"""
        return code.upper() == self.delivery_code.upper()


class DeliveryManager:
    """交付管理器"""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.tasks: Dict[str, DeliveryTask] = {}
        self.user_tasks: Dict[str, List[str]] = {}  # user_id -> [task_ids]

        # 可用配送节点
        self.available_couriers: Dict[str, Dict] = {}

        # 安全交付点
        self.safe_points: List[Dict] = []

        # 回调
        self.on_task_update: Optional[Callable] = None
        self.on_courier_arrived: Optional[Callable] = None

    def create_delivery_task(
        self,
        transaction_id: str,
        sender_id: str,
        receiver_id: str,
        product_id: str,
        product_snapshot: Dict,
        delivery_type: DeliveryType,
        pickup_info: Dict,
        dropoff_info: Dict,
        delivery_fee: float = 0.0,
    ) -> DeliveryTask:
        """创建交付任务"""
        task = DeliveryTask(
            transaction_id=transaction_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            product_id=product_id,
            product_snapshot=product_snapshot,
            delivery_type=delivery_type,
            pickup_address=pickup_info.get("address", ""),
            pickup_location=pickup_info.get("location", {}),
            dropoff_address=dropoff_info.get("address", ""),
            dropoff_location=dropoff_info.get("location", {}),
            delivery_fee=delivery_fee,
            scheduled_pickup_time=pickup_info.get("time", time.time() + 3600),
            scheduled_delivery_time=dropoff_info.get("time", time.time() + 7200),
        )

        # 生成验证码
        task.generate_codes()

        self.tasks[task.task_id] = task
        self._index_user_task(sender_id, task.task_id)
        self._index_user_task(receiver_id, task.task_id)

        return task

    def arrange_courier(self, task_id: str, courier_id: str) -> bool:
        """安排配送员"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.status != DeliveryStatus.PENDING:
            return False

        task.courier_id = courier_id
        task.status = DeliveryStatus.ARRANGED
        task.add_status_history(DeliveryStatus.ARRANGED, f"Courier {courier_id} assigned")
        task.update_timestamp()

        self._notify_update(task)

        return True

    def start_pickup(self, task_id: str) -> bool:
        """开始取货"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.status != DeliveryStatus.ARRANGED:
            return False

        if task.courier_id != self.node_id:
            return False

        task.status = DeliveryStatus.IN_TRANSIT
        task.actual_pickup_time = time.time()
        task.add_status_history(DeliveryStatus.IN_TRANSIT, "Package picked up")
        task.update_timestamp()

        self._notify_update(task)

        return True

    def confirm_pickup(self, task_id: str, code: str) -> bool:
        """确认取货（卖家确认）"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if not task.verify_pickup_code(code):
            return False

        # 配送员已取货
        if task.courier_id:
            task.status = DeliveryStatus.IN_TRANSIT
            task.actual_pickup_time = time.time()
            task.add_status_history(DeliveryStatus.IN_TRANSIT, "Picked up with verification")
        else:
            # 自提情况
            task.status = DeliveryStatus.ARRIVED
            task.add_status_history(DeliveryStatus.ARRIVED, "Self-pickup verified")

        task.update_timestamp()
        self._notify_update(task)

        return True

    def mark_arrived(self, task_id: str) -> bool:
        """标记已到达"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.status != DeliveryStatus.IN_TRANSIT:
            return False

        task.status = DeliveryStatus.ARRIVED
        task.add_status_history(DeliveryStatus.ARRIVED, "Arrived at destination")
        task.update_timestamp()

        self._notify_update(task)

        if self.on_courier_arrived:
            self.on_courier_arrived(task)

        return True

    def complete_delivery(self, task_id: str, code: str) -> bool:
        """完成交付"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if not task.verify_delivery_code(code):
            return False

        task.status = DeliveryStatus.COMPLETED
        task.actual_delivery_time = time.time()
        task.add_status_history(DeliveryStatus.COMPLETED, "Delivered and verified")
        task.update_timestamp()

        self._notify_update(task)

        return True

    def confirm_receipt(self, task_id: str) -> bool:
        """买家确认收货"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.status != DeliveryStatus.ARRIVED:
            return False

        if task.receiver_id != self.node_id:
            return False

        task.status = DeliveryStatus.COMPLETED
        task.actual_delivery_time = time.time()
        task.add_status_history(DeliveryStatus.COMPLETED, "Receipt confirmed by buyer")
        task.update_timestamp()

        self._notify_update(task)

        return True

    def fail_delivery(self, task_id: str, reason: str) -> bool:
        """交付失败"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        task.status = DeliveryStatus.FAILED
        task.add_status_history(DeliveryStatus.FAILED, reason)
        task.update_timestamp()

        self._notify_update(task)

        return True

    def cancel_delivery(self, task_id: str, reason: str = "") -> bool:
        """取消交付"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.status in [DeliveryStatus.COMPLETED, DeliveryStatus.CANCELLED, DeliveryStatus.FAILED]:
            return False

        task.status = DeliveryStatus.CANCELLED
        task.add_status_history(DeliveryStatus.CANCELLED, reason or "Cancelled by user")
        task.update_timestamp()

        self._notify_update(task)

        return True

    def get_task(self, task_id: str) -> Optional[DeliveryTask]:
        """获取任务"""
        return self.tasks.get(task_id)

    def get_my_tasks(self, as_sender: bool = True, as_receiver: bool = True, as_courier: bool = True) -> List[DeliveryTask]:
        """获取我的交付任务"""
        result = []

        for task in self.tasks.values():
            if as_sender and task.sender_id == self.node_id:
                result.append(task)
            elif as_receiver and task.receiver_id == self.node_id:
                result.append(task)
            elif as_courier and task.courier_id == self.node_id:
                result.append(task)

        result.sort(key=lambda x: x.updated_at, reverse=True)
        return result

    def get_pending_tasks(self) -> List[DeliveryTask]:
        """获取待处理任务（可抢单）"""
        return [
            task for task in self.tasks.values()
            if task.status == DeliveryStatus.PENDING
            and task.delivery_type == DeliveryType.DELIVERY
        ]

    def register_safe_point(self, location: Dict, name: str, hours: str = "9:00-21:00") -> str:
        """注册安全交付点"""
        point_id = hashlib.sha256(
            f"{location.get('lat', 0)}:{location.get('lon', 0)}:{time.time()}".encode()
        ).hexdigest()[:12]

        point = {
            "id": point_id,
            "name": name,
            "location": location,
            "hours": hours,
            "registered_at": time.time(),
        }

        self.safe_points.append(point)
        return point_id

    def find_nearest_safe_point(self, location: Dict, max_distance_km: float = 5.0) -> Optional[Dict]:
        """查找最近的安全交付点"""
        # 简化实现
        if not self.safe_points:
            return None

        def distance(loc1, loc2):
            # Haversine简化
            dlat = loc1.get('lat', 0) - loc2.get('lat', 0)
            dlon = loc1.get('lon', 0) - loc2.get('lon', 0)
            return (dlat**2 + dlon**2)**0.5 * 111  # 粗略转换

        nearest = None
        min_dist = max_distance_km

        for point in self.safe_points:
            dist = distance(location, point['location'])
            if dist < min_dist:
                min_dist = dist
                nearest = point

        return nearest

    def _index_user_task(self, user_id: str, task_id: str):
        """索引用户任务"""
        if user_id not in self.user_tasks:
            self.user_tasks[user_id] = []
        if task_id not in self.user_tasks[user_id]:
            self.user_tasks[user_id].append(task_id)

    def _notify_update(self, task: DeliveryTask):
        """通知更新"""
        if self.on_task_update:
            self.on_task_update(task)


if __name__ == "__main__":
    # 简单测试
    manager = DeliveryManager("seller_123")

    # 创建交付任务
    task = manager.create_delivery_task(
        transaction_id="tx_001",
        sender_id="seller_123",
        receiver_id="buyer_456",
        product_id="prod_789",
        product_snapshot={"title": "iPhone 14"},
        delivery_type=DeliveryType.DELIVERY,
        pickup_info={
            "address": "北京朝阳区某某路",
            "location": {"lat": 39.9, "lon": 116.4},
            "time": time.time() + 3600,
        },
        dropoff_info={
            "address": "北京海淀区某某街",
            "location": {"lat": 39.95, "lon": 116.3},
            "time": time.time() + 7200,
        },
        delivery_fee=15.0,
    )

    print(f"Delivery task created: {task.task_id}")
    print(f"Pickup code: {task.pickup_code}")
    print(f"Delivery code: {task.delivery_code}")
