"""
扩展交易数据结构 - Extended Transaction Data Structures

为"事件驱动账本"提供扩展的操作类型和数据结构

OpType 分组：
1. 积分类（原有）
2. 任务调度类
3. 跨租户消息类
4. 游戏资产类
5. 政务一码通类
6. 隐私保护类
"""

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from enum import Enum
from decimal import Decimal


class OpType(Enum):
    """
    操作类型枚举

    分组说明：
    - 积分类：原有的积分操作
    - 任务类：分布式任务调度防重放
    - 租户类：跨租户软隔离消息通道
    - 资产类：游戏资产全生命周期管理
    - 政务类：政务一码通实名事件
    - 隐私类：零知识证明相关
    """

    # ═══════════════════════════════════════════════════════════
    # 积分类（原有用例保持兼容）
    # ═══════════════════════════════════════════════════════════
    IN = "IN"                       # 积分收入（后台发放）
    OUT = "OUT"                     # 积分支出（消费）
    TRANSFER_IN = "TRANSFER_IN"     # 转账收入
    TRANSFER_OUT = "TRANSFER_OUT"   # 转账支出
    RECHARGE = "RECHARGE"           # 充值（微信/支付宝回调）

    # ═══════════════════════════════════════════════════════════
    # 任务调度类（替代 Redis 分布式锁）
    # 核心思路：任务执行 = 交易，biz_id = 任务ID
    # 防重放：同一任务ID只能被成功执行一次
    # ═══════════════════════════════════════════════════════════
    TASK_DISPATCH = "TASK_DISPATCH"     # 任务派发（创建任务）
    TASK_EXECUTE = "TASK_EXECUTE"       # 任务执行（开始处理）
    TASK_COMPLETE = "TASK_COMPLETE"     # 任务完成（成功结束）
    TASK_CANCEL = "TASK_CANCEL"         # 任务取消（失败/超时）
    TASK_RETRY = "TASK_RETRY"           # 任务重试

    # ═══════════════════════════════════════════════════════════
    # 跨租户消息类（SaaS 多租户数据隔离）
    # 核心思路：消息作为交易，tenant_id 作为域标识
    # 不可抵赖：A租户发出的消息，全网记账，B租户可验证真伪
    # ═══════════════════════════════════════════════════════════
    CROSS_TENANT_MSG = "CROSS_TENANT_MSG"   # 跨租户消息发送
    TENANT_NOTIFY = "TENANT_NOTIFY"          # 租户通知
    TENANT_RECEIPT = "TENANT_RECEIPT"       # 消息回执（确认收到）

    # ═══════════════════════════════════════════════════════════
    # 游戏资产类（非区块链版 Web3）
    # 核心思路：资产即交易，流转全网同步
    # 运营方无法单方面修改玩家资产（除非控制 51% 中继）
    # ═══════════════════════════════════════════════════════════
    ASSET_GRANT = "ASSET_GRANT"         # 资产发放（运营方->玩家）
    ASSET_TRANSFER = "ASSET_TRANSFER"   # 资产转让（玩家->玩家）
    ASSET_CONSUME = "ASSET_CONSUME"     # 资产消耗（使用/销毁）
    ASSET_FREEZE = "ASSET_FREEZE"       # 资产冻结
    ASSET_UNFREEZE = "ASSET_UNFREEZE"   # 资产解冻

    # ═══════════════════════════════════════════════════════════
    # 政务一码通类（南京本地化场景）
    # 核心思路：每个人员流动动作作为事件记录
    # 地铁进站/出站、图书借还、停车入场/出场
    # 防篡改：链式记录 + 多节点共识
    # ═══════════════════════════════════════════════════════════
    GOV_CHECKIN = "GOV_CHECKIN"         # 签到/入场（如地铁进站）
    GOV_CHECKOUT = "GOV_CHECKOUT"       # 签退/出场（如地铁出站）
    GOV_VERIFY = "GOV_VERIFY"           # 身份核验
    GOV_REVOKE = "GOV_REVOKE"           # 凭证撤销/取消
    GOV_TRANSFER = "GOV_TRANSFER"       # 权益转移（如老年卡余额转移）

    # ═══════════════════════════════════════════════════════════
    # 隐私保护类（零知识证明雏形）
    # 核心思路：证明"有权限执行"而不暴露"具体余额"
    # 适用于企业间结算的高隐私场景
    # ═══════════════════════════════════════════════════════════
    ZK_PROOF_SUBMIT = "ZK_PROOF_SUBMIT"     # 提交零知识证明
    ZK_PROOF_VERIFY = "ZK_PROOF_VERIFY"     # 验证零知识证明
    ZK_RANGE_PROOF = "ZK_RANGE_PROOF"       # 范围证明（证明余额在范围内）

    # ═══════════════════════════════════════════════════════════
    # 分布式 IM 类（消息账本）
    # 核心思路：消息即交易，每条消息都是一条链式记账
    # - 私聊：A发送给B的消息，A和B都有各自的链
    # - 群聊：群消息在群里广播
    # - 消息可编辑、删除（通过交易链追溯）
    # ═══════════════════════════════════════════════════════════
    MSG_SEND = "MSG_SEND"                   # 发送消息
    MSG_RECEIPT = "MSG_RECEIPT"             # 消息回执（已读/未读）
    MSG_EDIT = "MSG_EDIT"                   # 消息编辑
    MSG_DELETE = "MSG_DELETE"                # 消息删除（软删除）
    MSG_REACTION = "MSG_REACTION"            # 消息反应（emoji）
    MSG_REPLY = "MSG_REPLY"                  # 消息回复
    MSG_FORWARD = "MSG_FORWARD"              # 消息转发

    # ═══════════════════════════════════════════════════════════
    # 文件分享类（基于消息扩展）
    # 核心思路：文件元数据作为交易，文件内容通过 P2P 分片传播
    # ═══════════════════════════════════════════════════════════
    FILE_SHARE = "FILE_SHARE"               # 文件分享（发布文件元数据）
    FILE_REQUEST = "FILE_REQUEST"           # 文件请求（请求下载某个文件）
    FILE_SLICE_HASH = "FILE_SLICE_HASH"     # 文件分片哈希（BitTorrent 风格）

    # ═══════════════════════════════════════════════════════════
    # 通用事件类（扩展用）
    # ═══════════════════════════════════════════════════════════
    CUSTOM_EVENT = "CUSTOM_EVENT"           # 自定义业务事件


class OpCategory(Enum):
    """操作类别（用于分组）"""
    POINTS = "POINTS"           # 积分
    TASK = "TASK"               # 任务调度
    TENANT = "TENANT"           # 跨租户
    ASSET = "ASSET"             # 游戏资产
    GOV = "GOV"                 # 政务
    PRIVACY = "PRIVACY"         # 隐私
    IM = "IM"                   # 分布式IM
    FILE = "FILE"               # 文件分享
    GENERAL = "GENERAL"         # 通用


# 操作类别映射
OP_CATEGORY_MAP = {
    # 积分类
    OpType.IN: OpCategory.POINTS,
    OpType.OUT: OpCategory.POINTS,
    OpType.TRANSFER_IN: OpCategory.POINTS,
    OpType.TRANSFER_OUT: OpCategory.POINTS,
    OpType.RECHARGE: OpCategory.POINTS,

    # 任务类
    OpType.TASK_DISPATCH: OpCategory.TASK,
    OpType.TASK_EXECUTE: OpCategory.TASK,
    OpType.TASK_COMPLETE: OpCategory.TASK,
    OpType.TASK_CANCEL: OpCategory.TASK,
    OpType.TASK_RETRY: OpCategory.TASK,

    # 租户类
    OpType.CROSS_TENANT_MSG: OpCategory.TENANT,
    OpType.TENANT_NOTIFY: OpCategory.TENANT,
    OpType.TENANT_RECEIPT: OpCategory.TENANT,

    # 资产类
    OpType.ASSET_GRANT: OpCategory.ASSET,
    OpType.ASSET_TRANSFER: OpCategory.ASSET,
    OpType.ASSET_CONSUME: OpCategory.ASSET,
    OpType.ASSET_FREEZE: OpCategory.ASSET,
    OpType.ASSET_UNFREEZE: OpCategory.ASSET,

    # 政务类
    OpType.GOV_CHECKIN: OpCategory.GOV,
    OpType.GOV_CHECKOUT: OpCategory.GOV,
    OpType.GOV_VERIFY: OpCategory.GOV,
    OpType.GOV_REVOKE: OpCategory.GOV,
    OpType.GOV_TRANSFER: OpCategory.GOV,

    # 隐私类
    OpType.ZK_PROOF_SUBMIT: OpCategory.PRIVACY,
    OpType.ZK_PROOF_VERIFY: OpCategory.PRIVACY,
    OpType.ZK_RANGE_PROOF: OpCategory.PRIVACY,

    # IM类（分布式IM）
    OpType.MSG_SEND: OpCategory.IM,
    OpType.MSG_RECEIPT: OpCategory.IM,
    OpType.MSG_EDIT: OpCategory.IM,
    OpType.MSG_DELETE: OpCategory.IM,
    OpType.MSG_REACTION: OpCategory.IM,
    OpType.MSG_REPLY: OpCategory.IM,
    OpType.MSG_FORWARD: OpCategory.IM,

    # 文件类
    OpType.FILE_SHARE: OpCategory.FILE,
    OpType.FILE_REQUEST: OpCategory.FILE,
    OpType.FILE_SLICE_HASH: OpCategory.FILE,

    # 通用
    OpType.CUSTOM_EVENT: OpCategory.GENERAL,
}


def get_op_category(op_type: OpType) -> OpCategory:
    """获取操作类别"""
    return OP_CATEGORY_MAP.get(op_type, OpCategory.GENERAL)


def is_points_op(op_type: OpType) -> bool:
    """是否为积分操作"""
    return get_op_category(op_type) == OpCategory.POINTS


def is_task_op(op_type: OpType) -> bool:
    """是否为任务操作"""
    return get_op_category(op_type) == OpCategory.TASK


def is_asset_op(op_type: OpType) -> bool:
    """是否为资产操作"""
    return get_op_category(op_type) == OpCategory.ASSET


def is_im_op(op_type: OpType) -> bool:
    """是否为IM消息操作"""
    return get_op_category(op_type) == OpCategory.IM


def is_file_op(op_type: OpType) -> bool:
    """是否为文件操作"""
    return get_op_category(op_type) == OpCategory.FILE


def is_balance_mutating(op_type: OpType) -> bool:
    """
    是否会变更余额

    积分类：IN/RECHARGE 增加，OUT/TRANSFER_OUT 减少
    资产类：不涉及余额，但涉及资产归属
    任务类：涉及任务状态变更
    """
    return op_type in (
        OpType.IN,
        OpType.RECHARGE,
        OpType.TRANSFER_IN,
        OpType.OUT,
        OpType.TRANSFER_OUT,
    )


@dataclass
class EventTx:
    """
    事件交易

    扩展自原 Tx，增加了：
    - tenant_id: 租户ID（跨租户场景）
    - biz_id: 业务ID（任务ID/资产ID/消息ID）
    - metadata: 扩展元数据（JSON格式）
    - asset_type: 资产类型（游戏资产场景）

    核心字段说明：
    - tx_hash: 交易唯一标识（SHA256计算）
    - prev_tx_hash: 用户上一笔交易hash，形成哈希链
    - user_id: 用户/主体ID
    - op_type: 操作类型
    - amount: 数量（积分场景用 1.0，任务场景可忽略）

    防重放机制：
    - nonce: 用户级自增序号
    - biz_id: 业务级幂等（如任务ID、资产ID）
    """

    # ───────────────────────────────────────────────────────────
    # 核心标识
    # ───────────────────────────────────────────────────────────
    user_id: str                      # 用户/主体ID
    op_type: OpType                  # 操作类型
    amount: Decimal = Decimal("0")   # 数量（积分场景必须，任务/资产场景可设为1）

    # ───────────────────────────────────────────────────────────
    # 链式结构（防双花关键）
    # ───────────────────────────────────────────────────────────
    prev_tx_hash: str = ""           # 上一笔交易的hash，空表示第一笔

    # ───────────────────────────────────────────────────────────
    # 防重放机制
    # ───────────────────────────────────────────────────────────
    nonce: int = 0                   # 用户级自增序号

    # ───────────────────────────────────────────────────────────
    # 目标（转账/任务派发/资产转让用）
    # ───────────────────────────────────────────────────────────
    to_user_id: Optional[str] = None

    # ───────────────────────────────────────────────────────────
    # 业务标识（任务ID/资产ID/消息ID，用于防重放）
    # ───────────────────────────────────────────────────────────
    biz_id: str = ""                 # 业务ID（如任务ID）

    # ───────────────────────────────────────────────────────────
    # 扩展标识
    # ───────────────────────────────────────────────────────────
    tenant_id: str = ""              # 租户ID（多租户场景）
    asset_type: str = ""             # 资产类型（游戏资产场景）

    # ───────────────────────────────────────────────────────────
    # 元数据（JSON格式，扩展用）
    # ───────────────────────────────────────────────────────────
    metadata_json: str = ""          # 扩展元数据（JSON字符串）

    # ───────────────────────────────────────────────────────────
    # 节点信息
    # ───────────────────────────────────────────────────────────
    relay_id: Optional[str] = None   # 受理中继ID

    # ───────────────────────────────────────────────────────────
    # 时间戳
    # ───────────────────────────────────────────────────────────
    created_at: float = field(default_factory=time.time)

    # ───────────────────────────────────────────────────────────
    # 派生字段（自动计算）
    # ───────────────────────────────────────────────────────────
    tx_hash: str = ""                # 交易哈希，由系统计算
    signature: str = ""             # 签名（可选）

    def __post_init__(self):
        """初始化后计算tx_hash"""
        if not self.tx_hash:
            self.tx_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """
        计算交易哈希

        包含字段：
        - user_id: 主体标识
        - op_type: 操作类型
        - amount: 数量
        - nonce: 防重放序号
        - prev_tx_hash: 链式结构
        - biz_id: 业务标识（任务ID/资产ID）
        - tenant_id: 租户标识
        - created_at: 时间戳

        不包含 signature（防止签名伪造）
        """
        content = (
            f"{self.user_id}|{self.op_type.value}|{self.amount}|{self.nonce}|"
            f"{self.prev_tx_hash}|{self.to_user_id or ''}|{self.biz_id or ''}|"
            f"{self.tenant_id or ''}|{self.asset_type or ''}|{self.created_at}"
        )
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据字典"""
        if not self.metadata_json:
            return {}
        try:
            return json.loads(self.metadata_json)
        except json.JSONDecodeError:
            return {}

    def set_metadata(self, data: Dict[str, Any]):
        """设置元数据"""
        self.metadata_json = json.dumps(data, ensure_ascii=False)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "tx_hash": self.tx_hash,
            "user_id": self.user_id,
            "op_type": self.op_type.value,
            "amount": str(self.amount),
            "prev_tx_hash": self.prev_tx_hash,
            "nonce": self.nonce,
            "to_user_id": self.to_user_id,
            "biz_id": self.biz_id,
            "tenant_id": self.tenant_id,
            "asset_type": self.asset_type,
            "metadata": self.get_metadata(),
            "relay_id": self.relay_id,
            "created_at": self.created_at,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'EventTx':
        """从字典创建"""
        d = d.copy()

        # 处理 op_type
        if isinstance(d.get('op_type'), str):
            d['op_type'] = OpType(d['op_type'])

        # 处理 amount
        if isinstance(d.get('amount'), str):
            d['amount'] = Decimal(d['amount'])
        elif d.get('amount') is None:
            d['amount'] = Decimal("0")

        # 处理 metadata
        if 'metadata' in d and isinstance(d['metadata'], dict):
            d['metadata_json'] = json.dumps(d['metadata'], ensure_ascii=False)
            del d['metadata']

        # 删除 tx_hash 让其自动计算
        if 'tx_hash' in d:
            hash_value = d['tx_hash']
            d['tx_hash'] = ""

        tx = cls(**d)

        # 恢复 tx_hash（如果不指定则已自动计算）
        if 'tx_hash' in d and hash_value:
            tx.tx_hash = hash_value

        return tx

    def to_json(self) -> str:
        """序列化为JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> 'EventTx':
        """从JSON反序列化"""
        return cls.from_dict(json.loads(s))

    def verify_hash(self) -> bool:
        """验证哈希是否正确"""
        expected = self._compute_hash()
        return self.tx_hash == expected

    def __str__(self) -> str:
        """字符串表示"""
        op_symbol = "+" if self.op_type in (
            OpType.IN, OpType.TRANSFER_IN, OpType.RECHARGE,
            OpType.TASK_COMPLETE, OpType.TENANT_RECEIPT
        ) else "-"

        base = f"EventTx({self.tx_hash[:8]}... {self.user_id[:8]}... {self.op_type.value}"

        if self.biz_id:
            base += f" biz={self.biz_id[:8]}..."

        if self.amount and self.amount != Decimal("1"):
            base += f" {op_symbol}{self.amount}"

        base += f" nonce={self.nonce})"

        return base


@dataclass
class EventValidationResult:
    """事件校验结果"""
    valid: bool
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    category: OpCategory = OpCategory.GENERAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "error": self.error,
            "warnings": self.warnings,
            "category": self.category.value,
        }


class EventTxBuilder:
    """
    事件交易构建器

    提供各类业务场景的交易构建方法

    使用示例：

    # 构建任务派发交易
    task_dispatch = EventTxBuilder.build_task_dispatch(
        user_id="dispatcher_001",
        task_id="task_12345",
        nonce=0,
        prev_hash="",
        executor="worker_001",
        task_data={"command": "process_order"},
        tenant_id="tenant_a"
    )

    # 构建跨租户消息
    msg = EventTxBuilder.build_cross_tenant_msg(
        user_id="user_a001",
        to_user_id="user_b002",
        message="请确认订单#12345",
        biz_id="msg_unique_id",
        nonce=5,
        prev_hash="..."
    )
    """

    # ═══════════════════════════════════════════════════════════
    # 任务调度相关
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def build_task_dispatch(
        user_id: str,
        task_id: str,
        nonce: int,
        prev_tx_hash: str,
        executor: str,
        task_type: str = "general",
        task_data: Optional[Dict] = None,
        tenant_id: str = "",
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """
        构建任务派发交易

        Args:
            user_id: 派发者ID
            task_id: 任务ID（唯一标识，用于防重放）
            nonce: 派发者交易序号
            prev_tx_hash: 上一笔交易hash
            executor: 指定执行者ID
            task_type: 任务类型
            task_data: 任务参数
            tenant_id: 租户ID
            relay_id: 受理中继ID
        """
        tx = EventTx(
            user_id=user_id,
            op_type=OpType.TASK_DISPATCH,
            amount=Decimal("1"),  # 任务执行计数
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            to_user_id=executor,
            biz_id=task_id,
            tenant_id=tenant_id,
            relay_id=relay_id,
        )

        if task_data:
            tx.set_metadata({
                "task_type": task_type,
                "task_params": task_data,
            })

        return tx

    @staticmethod
    def build_task_execute(
        user_id: str,
        task_id: str,
        nonce: int,
        prev_tx_hash: str,
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """
        构建任务执行交易

        表示任务开始执行
        """
        return EventTx(
            user_id=user_id,
            op_type=OpType.TASK_EXECUTE,
            amount=Decimal("1"),
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            biz_id=task_id,
            relay_id=relay_id,
        )

    @staticmethod
    def build_task_complete(
        user_id: str,
        task_id: str,
        nonce: int,
        prev_tx_hash: str,
        result: str = "success",
        output: Optional[Dict] = None,
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """
        构建任务完成交易

        表示任务成功/失败完成
        """
        tx = EventTx(
            user_id=user_id,
            op_type=OpType.TASK_COMPLETE,
            amount=Decimal("1"),
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            biz_id=task_id,
            relay_id=relay_id,
        )

        if output:
            tx.set_metadata({
                "result": result,
                "output": output,
            })

        return tx

    @staticmethod
    def build_task_cancel(
        user_id: str,
        task_id: str,
        nonce: int,
        prev_tx_hash: str,
        reason: str,
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """
        构建任务取消交易
        """
        tx = EventTx(
            user_id=user_id,
            op_type=OpType.TASK_CANCEL,
            amount=Decimal("1"),
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            biz_id=task_id,
            relay_id=relay_id,
        )
        tx.set_metadata({"reason": reason})
        return tx

    # ═══════════════════════════════════════════════════════════
    # 跨租户消息相关
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def build_cross_tenant_msg(
        user_id: str,
        to_user_id: str,
        message: str,
        biz_id: str,
        nonce: int,
        prev_tx_hash: str,
        tenant_id: str = "",
        msg_type: str = "notification",
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """
        构建跨租户消息交易

        Args:
            user_id: 发送者ID
            to_user_id: 接收者ID
            message: 消息内容
            biz_id: 消息唯一ID（用于幂等性检查）
            nonce: 发送者交易序号
            prev_tx_hash: 上一笔交易hash
            tenant_id: 发送者租户ID
            msg_type: 消息类型
            relay_id: 受理中继ID
        """
        tx = EventTx(
            user_id=user_id,
            op_type=OpType.CROSS_TENANT_MSG,
            amount=Decimal("1"),
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            to_user_id=to_user_id,
            biz_id=biz_id,
            tenant_id=tenant_id,
            relay_id=relay_id,
        )
        tx.set_metadata({
            "message": message,
            "msg_type": msg_type,
        })
        return tx

    @staticmethod
    def build_tenant_receipt(
        user_id: str,
        original_msg_biz_id: str,
        nonce: int,
        prev_tx_hash: str,
        receipt_status: str = "received",
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """
        构建消息回执交易

        表示接收者已收到消息
        """
        tx = EventTx(
            user_id=user_id,
            op_type=OpType.TENANT_RECEIPT,
            amount=Decimal("1"),
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            biz_id=original_msg_biz_id,  # 引用原消息
            relay_id=relay_id,
        )
        tx.set_metadata({"receipt_status": receipt_status})
        return tx

    # ═══════════════════════════════════════════════════════════
    # 游戏资产相关
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def build_asset_grant(
        user_id: str,
        asset_id: str,
        asset_type: str,
        nonce: int,
        prev_tx_hash: str,
        grant_type: str = "login_reward",
        quantity: int = 1,
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """
        构建资产发放交易
        """
        tx = EventTx(
            user_id=user_id,
            op_type=OpType.ASSET_GRANT,
            amount=Decimal(quantity),
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            biz_id=asset_id,
            asset_type=asset_type,
            relay_id=relay_id,
        )
        tx.set_metadata({"grant_type": grant_type})
        return tx

    @staticmethod
    def build_asset_transfer(
        from_user: str,
        to_user: str,
        asset_id: str,
        asset_type: str,
        nonce: int,
        prev_tx_hash: str,
        price: Decimal = Decimal("0"),
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """
        构建资产转让交易（玩家之间）
        """
        tx = EventTx(
            user_id=from_user,
            op_type=OpType.ASSET_TRANSFER,
            amount=Decimal("1"),
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            to_user_id=to_user,
            biz_id=asset_id,
            asset_type=asset_type,
            relay_id=relay_id,
        )
        if price:
            tx.set_metadata({"price": str(price)})
        return tx

    @staticmethod
    def build_asset_consume(
        user_id: str,
        asset_id: str,
        nonce: int,
        prev_tx_hash: str,
        consume_type: str = "use",
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """
        构建资产消耗交易
        """
        tx = EventTx(
            user_id=user_id,
            op_type=OpType.ASSET_CONSUME,
            amount=Decimal("1"),
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            biz_id=asset_id,
            relay_id=relay_id,
        )
        tx.set_metadata({"consume_type": consume_type})
        return tx

    # ═══════════════════════════════════════════════════════════
    # 政务一码通相关
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def build_gov_checkin(
        user_id: str,
        card_id: str,
        location_id: str,
        location_type: str,
        nonce: int,
        prev_tx_hash: str,
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """
        构建签到/入场交易

        Args:
            user_id: 用户ID（可关联身份证）
            card_id: 卡号（一卡通卡号）
            location_id: 地点ID（如站点编号）
            location_type: 地点类型（metro/bus/library/parking）
            nonce: 交易序号
            prev_tx_hash: 上一笔交易hash
        """
        tx = EventTx(
            user_id=user_id,
            op_type=OpType.GOV_CHECKIN,
            amount=Decimal("1"),
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            biz_id=card_id,  # 卡号作为业务ID
            relay_id=relay_id,
        )
        tx.set_metadata({
            "location_id": location_id,
            "location_type": location_type,
            "action": "checkin",
        })
        return tx

    @staticmethod
    def build_gov_checkout(
        user_id: str,
        card_id: str,
        location_id: str,
        location_type: str,
        nonce: int,
        prev_tx_hash: str,
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """
        构建签退/出场交易
        """
        tx = EventTx(
            user_id=user_id,
            op_type=OpType.GOV_CHECKOUT,
            amount=Decimal("1"),
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            biz_id=card_id,
            relay_id=relay_id,
        )
        tx.set_metadata({
            "location_id": location_id,
            "location_type": location_type,
            "action": "checkout",
        })
        return tx

    # ═══════════════════════════════════════════════════════════
    # 积分类（兼容原有功能）
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def build_transfer(
        from_user: str,
        to_user: str,
        amount: Decimal,
        nonce: int,
        prev_tx_hash: str,
        memo: str = "",
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """构建转账交易"""
        return EventTx(
            user_id=from_user,
            op_type=OpType.TRANSFER_OUT,
            amount=amount,
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            to_user_id=to_user,
            relay_id=relay_id,
            memo=memo,
        )

    @staticmethod
    def build_grant(
        user_id: str,
        amount: Decimal,
        nonce: int,
        prev_tx_hash: str,
        memo: str = "",
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """构建积分发放交易"""
        return EventTx(
            user_id=user_id,
            op_type=OpType.IN,
            amount=amount,
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            relay_id=relay_id,
            memo=f"积分发放: {memo}",
        )

    @staticmethod
    def build_consume(
        user_id: str,
        amount: Decimal,
        nonce: int,
        prev_tx_hash: str,
        memo: str = "",
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """构建积分消费交易"""
        return EventTx(
            user_id=user_id,
            op_type=OpType.OUT,
            amount=amount,
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            relay_id=relay_id,
            memo=f"积分消费: {memo}",
        )

    @staticmethod
    def build_recharge(
        user_id: str,
        amount: Decimal,
        nonce: int,
        prev_tx_hash: str,
        payment_order_id: str,
        payment_channel: str = "wechat",
        memo: str = "",
        relay_id: Optional[str] = None,
    ) -> EventTx:
        """构建充值交易"""
        tx = EventTx(
            user_id=user_id,
            op_type=OpType.RECHARGE,
            amount=amount,
            prev_tx_hash=prev_tx_hash,
            nonce=nonce,
            biz_id=payment_order_id,
            relay_id=relay_id,
        )
        tx.set_metadata({
            "payment_channel": payment_channel,
            "memo": memo,
        })
        return tx