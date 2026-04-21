"""
游戏资产管理 - Game Asset Ledger

基于事件账本的分布式游戏资产管理，实现资产全生命周期可验证

核心思路：
1. 资产即交易：发放道具 = ASSET_GRANT 交易，转让道具 = ASSET_TRANSFER 交易
2. 真·玩家交易：玩家A转给B，生成 ASSET_TRANSFER 交易，账本全网同步
3. 运营方无法单方面修改：除非控制51%中继节点
4. 价值：给玩家提供"资产可验证"的安全感

对比传统方案：
| 特性 | 传统中心化 | 游戏资产账本 |
|------|-----------|-------------|
| 资产归属 | 运营方数据库 | 全网共识 |
| 交易透明度 | 黑盒操作 | 公开可验证 |
| 资产转移 | 运营方中转 | P2P直转 |
| 资产增发 | 随意增发 | 有限增发（规则共识）|
| 回滚风险 | 随时可回滚 | 难以回滚（需共识）|

使用示例：
```python
asset_ledger = GameAssetLedger(event_ledger)

# 运营方发放稀有道具给玩家
grant_tx = asset_ledger.grant_asset(
    issuer="game_admin",
    player="player_001",
    asset_id="weapon_legendary_001",
    asset_type="weapon",
    grant_type="login_reward"
)

# 玩家之间交易
transfer_tx = asset_ledger.transfer_asset(
    from_player="player_001",
    to_player="player_002",
    asset_id="weapon_legendary_001",
    price=Decimal("1000")  # 如果有价格
)

# 查询玩家资产
assets = asset_ledger.get_player_assets("player_001")

# 查询资产历史（溯源）
history = asset_ledger.get_asset_history("weapon_legendary_001")
```
"""

import time
import threading
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable, Any, Tuple, Set
from decimal import Decimal
from enum import Enum
from collections import defaultdict

from .event_transaction import EventTx, OpType, EventTxBuilder
from .event_ledger import EventLedger


class AssetType(Enum):
    """资产类型"""
    WEAPON = "weapon"           # 武器
    ARMOR = "armor"            # 防具
    CONSUMABLE = "consumable"   # 消耗品
    MATERIAL = "material"       # 材料
    CURRENCY = "currency"       # 货币（不建议直接用）
    PET = "pet"               # 宠物
    MOUNT = "mount"             # 坐骑
    TITLE = "title"            # 称号
    SKIN = "skin"              # 皮肤
    OTHER = "other"            # 其他


class GrantType(Enum):
    """发放类型"""
    PURCHASE = "purchase"       # 购买
    REWARD = "reward"           # 奖励
    LOGIN_REWARD = "login_reward"  # 登录奖励
    EVENT = "event"            # 活动
    GM = "gm"                  # GM发放
    TRADE = "trade"            # 交易市场


@dataclass
class AssetDefinition:
    """资产定义"""
    asset_id: str              # 资产唯一ID
    asset_type: AssetType      # 资产类型
    name: str = ""             # 资产名称
    rarity: str = "common"     # 稀有度：common/rare/epic/legendary
    max_supply: int = 0        # 最大供应量（0表示无限制）
    tradable: bool = True      # 是否可交易
    description: str = ""       # 描述


@dataclass
class AssetOwnership:
    """资产所有权"""
    asset_id: str
    asset_type: str
    owner: str                  # 当前拥有者
    previous_owners: List[str] = field(default_factory=list)  # 历史拥有者

    # 状态
    is_frozen: bool = False
    frozen_at: float = 0

    # 交易记录
    grant_tx: Optional[EventTx] = None
    latest_tx: Optional[EventTx] = None


@dataclass
class GameAssetLedger:
    """
    游戏资产账本

    基于事件账本管理游戏资产的全生命周期
    """

    def __init__(
        self,
        ledger: EventLedger,
        relay_id: Optional[str] = None,
    ):
        self.ledger = ledger
        self.relay_id = relay_id or "relay_default"

        # 资产定义
        self._asset_defs: Dict[str, AssetDefinition] = {}
        self._asset_defs_by_type: Dict[str, List[str]] = defaultdict(list)

        # 所有权缓存
        self._ownership: Dict[str, AssetOwnership] = {}
        self._player_assets: Dict[str, Set[str]] = defaultdict(set)  # player_id -> set(asset_id)

        self._lock = threading.RLock()

        # 回调
        self.on_asset_granted: Optional[Callable] = None
        self.on_asset_transferred: Optional[Callable] = None
        self.on_asset_consumed: Optional[Callable] = None

        # 预加载
        self._load_existing_assets()

    def _load_existing_assets(self):
        """加载已有资产"""
        for tx in self.ledger.txs.values():
            if tx.op_type == OpType.ASSET_GRANT:
                self._process_grant(tx)
            elif tx.op_type == OpType.ASSET_TRANSFER:
                self._process_transfer(tx)
            elif tx.op_type == OpType.ASSET_CONSUME:
                self._process_consume(tx)
            elif tx.op_type == OpType.ASSET_FREEZE:
                self._process_freeze(tx)
            elif tx.op_type == OpType.ASSET_UNFREEZE:
                self._process_unfreeze(tx)

    def _process_grant(self, tx: EventTx):
        """处理资产发放"""
        ownership = AssetOwnership(
            asset_id=tx.biz_id,
            asset_type=tx.asset_type,
            owner=tx.user_id,
            grant_tx=tx,
            latest_tx=tx,
        )
        self._ownership[tx.biz_id] = ownership
        self._player_assets[tx.user_id].add(tx.biz_id)

        # 注册资产定义
        if tx.biz_id not in self._asset_defs:
            metadata = tx.get_metadata()
            self._asset_defs[tx.biz_id] = AssetDefinition(
                asset_id=tx.biz_id,
                asset_type=AssetType(tx.asset_type) if tx.asset_type else AssetType.OTHER,
                name=metadata.get("name", tx.biz_id),
                rarity=metadata.get("rarity", "common"),
            )

    def _process_transfer(self, tx: EventTx):
        """处理资产转让"""
        if tx.biz_id not in self._ownership:
            return

        ownership = self._ownership[tx.biz_id]

        # 更新历史拥有者
        if ownership.owner not in ownership.previous_owners:
            ownership.previous_owners.append(ownership.owner)

        # 从原拥有者移除
        self._player_assets[ownership.owner].discard(tx.biz_id)

        # 更新拥有者
        ownership.owner = tx.user_id
        ownership.latest_tx = tx

        # 添加到新拥有者
        self._player_assets[tx.user_id].add(tx.biz_id)

    def _process_consume(self, tx: EventTx):
        """处理资产消耗"""
        if tx.biz_id not in self._ownership:
            return

        ownership = self._ownership[tx.biz_id]
        ownership.previous_owners.append(ownership.owner)
        self._player_assets[ownership.owner].discard(tx.biz_id)
        ownership.latest_tx = tx

        # 从所有权缓存移除（已消耗）
        del self._ownership[tx.biz_id]

    def _process_freeze(self, tx: EventTx):
        """处理资产冻结"""
        if tx.biz_id in self._ownership:
            self._ownership[tx.biz_id].is_frozen = True
            self._ownership[tx.biz_id].frozen_at = tx.created_at
            self._ownership[tx.biz_id].latest_tx = tx

    def _process_unfreeze(self, tx: EventTx):
        """处理资产解冻"""
        if tx.biz_id in self._ownership:
            self._ownership[tx.biz_id].is_frozen = False
            self._ownership[tx.biz_id].latest_tx = tx

    # ───────────────────────────────────────────────────────────
    # 资产操作
    # ───────────────────────────────────────────────────────────

    def register_asset_type(
        self,
        asset_id: str,
        asset_type: AssetType,
        name: str = "",
        rarity: str = "common",
        max_supply: int = 0,
        tradable: bool = True,
    ) -> bool:
        """
        注册资产类型

        Args:
            asset_id: 资产类型ID（如 "weapon_sword"）
            asset_type: 资产大类
            name: 名称
            rarity: 稀有度
            max_supply: 最大供应量
            tradable: 是否可交易

        Returns:
            是否成功
        """
        with self._lock:
            if asset_id in self._asset_defs:
                return False

            defn = AssetDefinition(
                asset_id=asset_id,
                asset_type=asset_type,
                name=name or asset_id,
                rarity=rarity,
                max_supply=max_supply,
                tradable=tradable,
            )
            self._asset_defs[asset_id] = defn
            self._asset_defs_by_type[asset_type.value].append(asset_id)
            return True

    def grant_asset(
        self,
        issuer: str,
        player: str,
        asset_id: str,
        asset_type: str,
        grant_type: str = "reward",
        quantity: int = 1,
        rarity: str = "common",
        name: str = "",
        metadata: Optional[Dict] = None,
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """
        发放资产给玩家

        Args:
            issuer: 发放者（如 game_admin）
            player: 目标玩家
            asset_id: 资产ID（唯一标识）
            asset_type: 资产类型
            grant_type: 发放类型
            quantity: 数量（目前支持1）
            rarity: 稀有度
            name: 资产名称
            metadata: 扩展元数据

        Returns:
            (success, message, tx)
        """
        with self._lock:
            # 1. 检查资产是否已存在
            if asset_id in self._ownership:
                return False, f"资产{asset_id}已存在", None

            # 2. 获取发放者状态
            nonce = self.ledger.get_nonce(issuer)
            prev_hash = self.ledger.get_prev_hash(issuer)

            # 3. 构建发放交易
            tx = EventTxBuilder.build_asset_grant(
                user_id=player,
                asset_id=asset_id,
                asset_type=asset_type,
                nonce=nonce,
                prev_tx_hash=prev_hash,
                grant_type=grant_type,
                quantity=quantity,
                relay_id=self.relay_id,
            )

            # 添加元数据
            meta = tx.get_metadata()
            meta["rarity"] = rarity
            meta["name"] = name or asset_id
            if metadata:
                meta.update(metadata)
            tx.set_metadata(meta)

            # 4. 提交账本
            ok, msg = self.ledger.add_tx(tx)
            if not ok:
                return False, f"账本提交失败: {msg}", None

            # 5. 更新所有权缓存
            self._process_grant(tx)

            # 6. 触发回调
            if self.on_asset_granted:
                try:
                    self.on_asset_granted(tx, player)
                except Exception:
                    pass

            return True, f"资产已发放给{player}", tx

    def transfer_asset(
        self,
        from_player: str,
        to_player: str,
        asset_id: str,
        price: Optional[Decimal] = None,
        transfer_type: str = "gift",
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """
        转让资产给其他玩家

        Args:
            from_player: 转出玩家
            to_player: 转入玩家
            asset_id: 资产ID
            price: 价格（可选）
            transfer_type: 转让类型

        Returns:
            (success, message, tx)
        """
        with self._lock:
            # 1. 检查资产是否存在
            if asset_id not in self._ownership:
                return False, f"资产{asset_id}不存在", None

            ownership = self._ownership[asset_id]

            # 2. 检查拥有者
            if ownership.owner != from_player:
                return False, f"玩家{from_player}不拥有此资产", None

            # 3. 检查是否冻结
            if ownership.is_frozen:
                return False, "资产已冻结，无法转让", None

            # 4. 获取转出者状态
            nonce = self.ledger.get_nonce(from_player)
            prev_hash = self.ledger.get_prev_hash(from_player)

            # 5. 获取资产类型
            defn = self._asset_defs.get(asset_id)
            if defn and not defn.tradable:
                return False, "此资产不可交易", None

            asset_type = ownership.asset_type or (defn.asset_type.value if defn else "other")

            # 6. 构建转让交易
            tx = EventTxBuilder.build_asset_transfer(
                from_user=from_player,
                to_user=to_player,
                asset_id=asset_id,
                asset_type=asset_type,
                nonce=nonce,
                prev_tx_hash=prev_hash,
                price=price or Decimal("0"),
                relay_id=self.relay_id,
            )

            # 添加元数据
            meta = tx.get_metadata()
            meta["transfer_type"] = transfer_type
            tx.set_metadata(meta)

            # 7. 提交账本
            ok, msg = self.ledger.add_tx(tx)
            if not ok:
                return False, f"账本提交失败: {msg}", None

            # 8. 更新所有权缓存
            self._process_transfer(tx)

            # 9. 触发回调
            if self.on_asset_transferred:
                try:
                    self.on_asset_transferred(tx, from_player, to_player)
                except Exception:
                    pass

            return True, f"资产已转让给{to_player}", tx

    def consume_asset(
        self,
        player: str,
        asset_id: str,
        consume_type: str = "use",
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """
        消耗/使用资产

        Args:
            player: 玩家
            asset_id: 资产ID
            consume_type: 消耗类型

        Returns:
            (success, message, tx)
        """
        with self._lock:
            if asset_id not in self._ownership:
                return False, f"资产{asset_id}不存在", None

            ownership = self._ownership[asset_id]

            if ownership.owner != player:
                return False, f"玩家{player}不拥有此资产", None

            if ownership.is_frozen:
                return False, "资产已冻结，无法消耗", None

            nonce = self.ledger.get_nonce(player)
            prev_hash = self.ledger.get_prev_hash(player)

            tx = EventTxBuilder.build_asset_consume(
                user_id=player,
                asset_id=asset_id,
                nonce=nonce,
                prev_tx_hash=prev_hash,
                consume_type=consume_type,
                relay_id=self.relay_id,
            )

            ok, msg = self.ledger.add_tx(tx)
            if not ok:
                return False, f"账本提交失败: {msg}", None

            self._process_consume(tx)

            if self.on_asset_consumed:
                try:
                    self.on_asset_consumed(tx, player)
                except Exception:
                    pass

            return True, "资产已消耗", tx

    def freeze_asset(
        self,
        operator: str,
        asset_id: str,
        reason: str = "",
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """冻结资产"""
        with self._lock:
            if asset_id not in self._ownership:
                return False, f"资产{asset_id}不存在", None

            ownership = self._ownership[asset_id]

            nonce = self.ledger.get_nonce(operator)
            prev_hash = self.ledger.get_prev_hash(operator)

            tx = EventTx(
                user_id=operator,
                op_type=OpType.ASSET_FREEZE,
                amount=Decimal("1"),
                prev_tx_hash=prev_hash,
                nonce=nonce,
                biz_id=asset_id,
                relay_id=self.relay_id,
            )
            tx.set_metadata({"reason": reason})

            ok, msg = self.ledger.add_tx(tx)
            if not ok:
                return False, f"账本提交失败: {msg}", None

            self._process_freeze(tx)
            return True, "资产已冻结", tx

    def unfreeze_asset(
        self,
        operator: str,
        asset_id: str,
    ) -> Tuple[bool, str, Optional[EventTx]]:
        """解冻资产"""
        with self._lock:
            if asset_id not in self._ownership:
                return False, f"资产{asset_id}不存在", None

            ownership = self._ownership[asset_id]

            nonce = self.ledger.get_nonce(operator)
            prev_hash = self.ledger.get_prev_hash(operator)

            tx = EventTx(
                user_id=operator,
                op_type=OpType.ASSET_UNFREEZE,
                amount=Decimal("1"),
                prev_tx_hash=prev_hash,
                nonce=nonce,
                biz_id=asset_id,
                relay_id=self.relay_id,
            )

            ok, msg = self.ledger.add_tx(tx)
            if not ok:
                return False, f"账本提交失败: {msg}", None

            self._process_unfreeze(tx)
            return True, "资产已解冻", tx

    # ───────────────────────────────────────────────────────────
    # 查询
    # ───────────────────────────────────────────────────────────

    def get_asset(self, asset_id: str) -> Optional[AssetOwnership]:
        """获取资产所有权信息"""
        return self._ownership.get(asset_id)

    def get_asset_def(self, asset_id: str) -> Optional[AssetDefinition]:
        """获取资产定义"""
        return self._asset_defs.get(asset_id)

    def get_player_assets(
        self,
        player_id: str,
        asset_type: Optional[str] = None,
        include_frozen: bool = True,
    ) -> List[AssetOwnership]:
        """获取玩家拥有的资产"""
        asset_ids = self._player_assets.get(player_id, set())
        result = []

        for asset_id in asset_ids:
            if asset_id not in self._ownership:
                continue

            ownership = self._ownership[asset_id]

            if not include_frozen and ownership.is_frozen:
                continue

            if asset_type and ownership.asset_type != asset_type:
                continue

            result.append(ownership)

        return result

    def get_asset_history(self, asset_id: str) -> List[EventTx]:
        """获取资产的完整历史（溯源）"""
        return self.ledger.get_biz_txs(asset_id)

    def get_asset_owners(self, asset_type: Optional[str] = None) -> Dict[str, str]:
        """
        获取所有资产及其拥有者

        Returns:
            {asset_id: owner_id, ...}
        """
        result = {}
        for asset_id, ownership in self._ownership.items():
            if asset_type and ownership.asset_type != asset_type:
                continue
            result[asset_id] = ownership.owner
        return result

    def get_richest_players(self, limit: int = 10) -> List[Tuple[str, int]]:
        """
        获取最富有的玩家（按资产数量）

        Returns:
            [(player_id, asset_count), ...]
        """
        rankings = []
        for player_id, asset_ids in self._player_assets.items():
            count = len([a for a in asset_ids if a in self._ownership])
            if count > 0:
                rankings.append((player_id, count))

        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings[:limit]

    def verify_asset_chain(self, asset_id: str) -> Tuple[bool, str, List[EventTx]]:
        """
        验证资产链完整性

        Returns:
            (is_valid, message, history_txs)
        """
        history = self.get_asset_history(asset_id)

        if not history:
            return False, f"资产{asset_id}不存在", []

        # 按nonce排序
        history_sorted = sorted(history, key=lambda x: x.nonce)

        # 检查是否有GRANT
        has_grant = any(tx.op_type == OpType.ASSET_GRANT for tx in history_sorted)
        if not has_grant:
            return False, "缺少资产发放记录", history_sorted

        # 检查拥有者链是否一致
        expected_owner = None
        for tx in history_sorted:
            if tx.op_type == OpType.ASSET_GRANT:
                expected_owner = tx.user_id
            elif tx.op_type == OpType.ASSET_TRANSFER:
                if tx.user_id != expected_owner:
                    return False, f"转让链断裂: 期望{expected_owner}, 实际{tx.user_id}", history_sorted
                expected_owner = tx.to_user_id

        return True, "资产链完整", history_sorted

    # ───────────────────────────────────────────────────────────
    # 统计
    # ───────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取资产统计"""
        total_assets = len(self._ownership)
        frozen_assets = sum(1 for o in self._ownership.values() if o.is_frozen)
        total_players = len(self._player_assets)

        by_type = defaultdict(int)
        for ownership in self._ownership.values():
            by_type[ownership.asset_type] += 1

        return {
            "total_assets": total_assets,
            "frozen_assets": frozen_assets,
            "total_players": total_players,
            "by_type": dict(by_type),
        }