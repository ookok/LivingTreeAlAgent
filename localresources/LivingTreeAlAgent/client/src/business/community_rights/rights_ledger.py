"""
权益账本模块 - RightsLedger
============================

核心功能：记录所有用户数字权益，确保不可转让、不可变现

设计原则：
1. 积分永不兑现现金
2. 权益不可转让、不可交易、不可变现
3. 平台可回收权益
4. 所有操作可审计

Author: Hermes Desktop Team
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set
from enum import Enum
from datetime import datetime, timedelta
import hashlib
import json
import uuid
import logging

logger = logging.getLogger(__name__)


class RightType(Enum):
    """权益类型 - 明确非金融属性"""
    SERVICE_QUOTA = "service_quota"           # 服务配额（AI调用次数、路由加速时长等）
    DIGITAL_ASSET = "digital_asset"           # 数字资产（专属皮肤、徽章、主题等）
    PLATFORM_PRIVILEGE = "platform_privilege" # 平台特权（优先体验、专属客服等）
    PHYSICAL_GOODS = "physical_goods"        # 实物商品（平台定制周边，需单独报备）


class RightSource(Enum):
    """权益来源"""
    COMMUNITY_FUND = "community_fund"  # 社区基金赠予
    EARN = "earn"                        # 用户积分兑换
    PURCHASE = "purchase"                # 购买获得
    PROMOTION = "promotion"              # 活动奖励


@dataclass
class DigitalRight:
    """
    数字权益 - 不可转让、不可变现

    重要属性：
    - transferable: 是否可转让（永远False）
    - tradable: 是否可交易（永远False）
    - revocable: 平台是否可以回收（默认True）
    """
    id: str
    user_id: str
    right_type: RightType
    name: str                           # 权益名称
    value: Dict                         # 权益具体内容
    granted_at: datetime
    expires_at: Optional[datetime] = None
    source: RightSource = RightSource.COMMUNITY_FUND
    metadata: Dict = field(default_factory=dict)

    # 不可转让属性（硬编码）
    transferable: bool = False
    tradable: bool = False
    revocable: bool = True              # 平台可回收

    # 税务信息
    cost_to_platform: float = 0.0       # 平台成本（含税）
    tax_paid: float = 0.0              # 已纳税款

    def __post_init__(self):
        if not self.id:
            self.id = f"right_{uuid.uuid4().hex[:16]}"

    @property
    def is_expired(self) -> bool:
        """检查权益是否过期"""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at

    @property
    def remaining_days(self) -> Optional[int]:
        """剩余有效天数"""
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.now()
        return max(0, delta.days)

    def to_dict(self) -> Dict:
        """转换为字典"""
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'right_type': self.right_type.value,
            'name': self.name,
            'value': self.value,
            'granted_at': self.granted_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'source': self.source.value,
            'metadata': self.metadata,
            'transferable': self.transferable,
            'tradable': self.tradable,
            'revocable': self.revocable,
            'cost_to_platform': self.cost_to_platform,
            'tax_paid': self.tax_paid,
            'is_expired': self.is_expired,
            'remaining_days': self.remaining_days,
        }
        return data

    def to_transfer_dict(self) -> Dict:
        """转换为不可篡改的传输格式（含哈希）"""
        data = self.to_dict()
        data['right_type'] = self.right_type.value
        data['source'] = self.source.value

        # 生成防篡改哈希
        data_str = json.dumps({k: v for k, v in data.items()
                               if k not in ['_hash', 'is_expired', 'remaining_days']},
                              sort_keys=True, ensure_ascii=False)
        data['_hash'] = hashlib.sha256(data_str.encode()).hexdigest()

        return data

    def get_terms(self) -> str:
        """获取权益条款"""
        return "本权益不可转让、不可交易、不可变现，平台保留最终解释权。"


@dataclass
class RightDefinition:
    """权益定义模板"""
    right_id: str
    name: str
    right_type: RightType
    description: str
    cost_to_platform: float              # 平台成本（含税）
    value: Dict                          # 权益内容
    valid_days: int = 365                # 默认有效期
    requires_credits: Optional[int] = None  # 需要多少积分兑换（None表示只能通过基金获得）
    max_issue_per_user: int = 999        # 单用户最高发放数量


class RightsLedger:
    """
    权益账本 - 记录所有用户权益

    功能：
    1. 权益发放、查询、撤销
    2. 权益类型合规验证
    3. 权益使用记录
    4. 权益过期管理
    """

    # 内置权益定义
    BUILTIN_RIGHTS: Dict[str, RightDefinition] = {
        'ai_quota_1k': RightDefinition(
            right_id='ai_quota_1k',
            name='AI服务额度1000次',
            right_type=RightType.SERVICE_QUOTA,
            description='AI智能助手服务1000次调用额度',
            cost_to_platform=10.00,
            value={'ai_calls': 1000, 'valid_days': 365},
            valid_days=365,
        ),
        'ai_quota_5k': RightDefinition(
            right_id='ai_quota_5k',
            name='AI服务额度5000次',
            right_type=RightType.SERVICE_QUOTA,
            description='AI智能助手服务5000次调用额度',
            cost_to_platform=45.00,
            value={'ai_calls': 5000, 'valid_days': 365},
            valid_days=365,
        ),
        'router_boost_30d': RightDefinition(
            right_id='router_boost_30d',
            name='智能路由加速30天',
            right_type=RightType.SERVICE_QUOTA,
            description='开启智能路由加速功能30天',
            cost_to_platform=15.00,
            value={'router_boost': True, 'days': 30},
            valid_days=30,
        ),
        'router_boost_90d': RightDefinition(
            right_id='router_boost_90d',
            name='智能路由加速90天',
            right_type=RightType.SERVICE_QUOTA,
            description='开启智能路由加速功能90天',
            cost_to_platform=40.00,
            value={'router_boost': True, 'days': 90},
            valid_days=90,
        ),
        'exclusive_badge': RightDefinition(
            right_id='exclusive_badge',
            name='社区共建者徽章',
            right_type=RightType.DIGITAL_ASSET,
            description='专属社区共建者荣誉徽章',
            cost_to_platform=0.00,
            value={'badge_id': 'community_builder', 'rarity': 'epic'},
            valid_days=365 * 10,  # 10年
        ),
        'founder_badge': RightDefinition(
            right_id='founder_badge',
            name='创始成员徽章',
            right_type=RightType.DIGITAL_ASSET,
            description='平台创始成员专属纪念徽章',
            cost_to_platform=0.00,
            value={'badge_id': 'founder', 'rarity': 'legendary'},
            valid_days=365 * 100,  # 永久
        ),
        'priority_support': RightDefinition(
            right_id='priority_support',
            name='优先客服通道',
            right_type=RightType.PLATFORM_PRIVILEGE,
            description='享受7x24小时优先客服服务',
            cost_to_platform=50.00,
            value={'support_level': 'priority', 'valid_days': 180},
            valid_days=180,
        ),
        'beta_feature': RightDefinition(
            right_id='beta_feature',
            name='新功能优先体验',
            right_type=RightType.PLATFORM_PRIVILEGE,
            description='优先体验平台最新内测功能',
            cost_to_platform=0.00,
            value={'beta_access': True, 'valid_days': 365},
            valid_days=365,
        ),
        'custom_theme': RightDefinition(
            right_id='custom_theme',
            name='专属定制主题',
            right_type=RightType.DIGITAL_ASSET,
            description='平台专属定制UI主题皮肤',
            cost_to_platform=5.00,
            value={'theme_id': 'custom', 'valid_days': 365},
            valid_days=365,
        ),
    }

    def __init__(self, db_path: str = "./data/rights_ledger.db"):
        """
        初始化权益账本

        Args:
            db_path: SQLite数据库路径
        """
        self.db_path = db_path
        self._init_database()
        self._cache: Dict[str, List[DigitalRight]] = {}

    def _init_database(self):
        """初始化数据库"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 用户权益表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_rights (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                right_type TEXT NOT NULL,
                name TEXT NOT NULL,
                value TEXT NOT NULL,
                granted_at TEXT NOT NULL,
                expires_at TEXT,
                source TEXT NOT NULL,
                metadata TEXT,
                cost_to_platform REAL DEFAULT 0.0,
                tax_paid REAL DEFAULT 0.0,
                revoked INTEGER DEFAULT 0,
                revoked_at TEXT,
                revoked_reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 权益使用记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS right_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                right_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                usage_type TEXT NOT NULL,
                usage_detail TEXT,
                used_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (right_id) REFERENCES user_rights(id)
            )
        """)

        # 权益定义表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS right_definitions (
                right_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                right_type TEXT NOT NULL,
                description TEXT,
                cost_to_platform REAL DEFAULT 0.0,
                value TEXT NOT NULL,
                valid_days INTEGER DEFAULT 365,
                requires_credits INTEGER,
                max_issue_per_user INTEGER DEFAULT 999
            )
        """)

        conn.commit()
        conn.close()
        logger.info(f"权益账本数据库初始化完成: {self.db_path}")

    def _get_connection(self):
        """获取数据库连接"""
        import sqlite3
        return sqlite3.connect(self.db_path)

    async def grant_right(self, user_id: str, right: DigitalRight) -> bool:
        """
        发放权益给用户

        Args:
            user_id: 用户ID
            right: 数字权益

        Returns:
            bool: 是否发放成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 插入权益记录
            cursor.execute("""
                INSERT INTO user_rights
                (id, user_id, right_type, name, value, granted_at, expires_at,
                 source, metadata, cost_to_platform, tax_paid)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                right.id,
                user_id,
                right.right_type.value,
                right.name,
                json.dumps(right.value),
                right.granted_at.isoformat(),
                right.expires_at.isoformat() if right.expires_at else None,
                right.source.value,
                json.dumps(right.metadata or {}),
                right.cost_to_platform,
                right.tax_paid,
            ))

            conn.commit()
            conn.close()

            # 清除缓存
            if user_id in self._cache:
                del self._cache[user_id]

            logger.info(f"权益发放成功: user_id={user_id}, right_id={right.id}, name={right.name}")
            return True

        except Exception as e:
            logger.error(f"权益发放失败: {e}")
            return False

    async def grant_right_by_type(self, user_id: str, right_type_id: str,
                                  source: RightSource = RightSource.COMMUNITY_FUND,
                                  tax_info: Dict = None) -> Optional[DigitalRight]:
        """
        根据权益类型发放权益

        Args:
            user_id: 用户ID
            right_type_id: 权益类型ID（如'ai_quota_1k'）
            source: 来源
            tax_info: 税务信息

        Returns:
            DigitalRight: 发放的权益，失败返回None
        """
        if right_type_id not in self.BUILTIN_RIGHTS:
            logger.error(f"未知的权益类型: {right_type_id}")
            return None

        definition = self.BUILTIN_RIGHTS[right_type_id]
        now = datetime.now()

        right = DigitalRight(
            id=f"right_{uuid.uuid4().hex[:16]}",
            user_id=user_id,
            right_type=definition.right_type,
            name=definition.name,
            value=definition.value,
            granted_at=now,
            expires_at=now + timedelta(days=definition.valid_days),
            source=source,
            metadata={'definition_id': right_type_id},
            cost_to_platform=definition.cost_to_platform,
            tax_paid=tax_info.get('tax_amount', 0) if tax_info else 0,
        )

        if await self.grant_right(user_id, right):
            return right
        return None

    async def batch_grant_rights(self, grants: List[Dict]) -> Dict[str, bool]:
        """
        批量发放权益

        Args:
            grants: 发放列表 [{user_id, right_type_id, source, tax_info}, ...]

        Returns:
            Dict: user_id -> 是否成功
        """
        results = {}
        for grant in grants:
            right = await self.grant_right_by_type(
                user_id=grant['user_id'],
                right_type_id=grant['right_type_id'],
                source=grant.get('source', RightSource.COMMUNITY_FUND),
                tax_info=grant.get('tax_info'),
            )
            results[grant['user_id']] = right is not None
        return results

    async def get_user_rights(self, user_id: str, include_expired: bool = False) -> List[DigitalRight]:
        """
        获取用户所有权益

        Args:
            user_id: 用户ID
            include_expired: 是否包含已过期的权益

        Returns:
            List[DigitalRight]: 权益列表
        """
        # 检查缓存
        if user_id in self._cache and include_expired:
            return self._cache[user_id]

        conn = self._get_connection()
        cursor = conn.cursor()

        if include_expired:
            cursor.execute("""
                SELECT id, user_id, right_type, name, value, granted_at, expires_at,
                       source, metadata, cost_to_platform, tax_paid
                FROM user_rights
                WHERE user_id = ? AND revoked = 0
                ORDER BY granted_at DESC
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT id, user_id, right_type, name, value, granted_at, expires_at,
                       source, metadata, cost_to_platform, tax_paid
                FROM user_rights
                WHERE user_id = ? AND revoked = 0
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY granted_at DESC
            """, (user_id, datetime.now().isoformat()))

        rows = cursor.fetchall()
        conn.close()

        rights = []
        for row in rows:
            right = DigitalRight(
                id=row[0],
                user_id=row[1],
                right_type=RightType(row[2]),
                name=row[3],
                value=json.loads(row[4]),
                granted_at=datetime.fromisoformat(row[5]),
                expires_at=datetime.fromisoformat(row[6]) if row[6] else None,
                source=RightSource(row[7]),
                metadata=json.loads(row[8]) if row[8] else {},
                cost_to_platform=row[9],
                tax_paid=row[10],
            )
            rights.append(right)

        # 更新缓存
        if include_expired:
            self._cache[user_id] = rights

        return rights

    async def get_user_rights_summary(self, user_id: str) -> Dict:
        """
        获取用户权益摘要

        Returns:
            Dict: {right_type: count, ...}
        """
        rights = await self.get_user_rights(user_id)

        summary = {
            'total_count': len(rights),
            'by_type': {},
            'by_source': {},
            'total_cost': 0.0,
            'total_tax': 0.0,
        }

        for right in rights:
            # 按类型统计
            type_key = right.right_type.value
            if type_key not in summary['by_type']:
                summary['by_type'][type_key] = 0
            summary['by_type'][type_key] += 1

            # 按来源统计
            source_key = right.source.value
            if source_key not in summary['by_source']:
                summary['by_source'][source_key] = 0
            summary['by_source'][source_key] += 1

            # 成本统计
            summary['total_cost'] += right.cost_to_platform
            summary['total_tax'] += right.tax_paid

        return summary

    async def revoke_right(self, right_id: str, reason: str = None) -> bool:
        """
        撤销用户权益

        Args:
            right_id: 权益ID
            reason: 撤销原因

        Returns:
            bool: 是否撤销成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE user_rights
                SET revoked = 1, revoked_at = ?, revoked_reason = ?
                WHERE id = ? AND revoked = 0
            """, (datetime.now().isoformat(), reason, right_id))

            affected = cursor.rowcount
            conn.commit()
            conn.close()

            if affected > 0:
                logger.info(f"权益撤销成功: right_id={right_id}, reason={reason}")
                return True
            return False

        except Exception as e:
            logger.error(f"权益撤销失败: {e}")
            return False

    async def use_right(self, right_id: str, user_id: str,
                         usage_type: str, usage_detail: str = None) -> bool:
        """
        记录权益使用

        Args:
            right_id: 权益ID
            user_id: 用户ID
            usage_type: 使用类型
            usage_detail: 使用详情

        Returns:
            bool: 是否记录成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO right_usage (right_id, user_id, usage_type, usage_detail)
                VALUES (?, ?, ?, ?)
            """, (right_id, user_id, usage_type, usage_detail))

            conn.commit()
            conn.close()

            logger.info(f"权益使用记录: right_id={right_id}, usage_type={usage_type}")
            return True

        except Exception as e:
            logger.error(f"权益使用记录失败: {e}")
            return False

    async def get_right_definitions(self) -> Dict[str, RightDefinition]:
        """获取所有权益定义"""
        return self.BUILTIN_RIGHTS.copy()

    async def check_right_available(self, user_id: str, right_type_id: str) -> bool:
        """
        检查用户是否有指定权益

        Args:
            user_id: 用户ID
            right_type_id: 权益类型ID

        Returns:
            bool: 是否有可用权益
        """
        rights = await self.get_user_rights(user_id)
        for right in rights:
            if right.value.get('definition_id') == right_type_id and not right.is_expired:
                return True
        return False

    def get_all_rights_for_display(self) -> List[Dict]:
        """获取所有权益定义（用于UI展示）"""
        result = []
        for rid, definition in self.BUILTIN_RIGHTS.items():
            result.append({
                'id': rid,
                'name': definition.name,
                'type': definition.right_type.value,
                'description': definition.description,
                'cost': definition.cost_to_platform,
            })
        return result


# 全局单例
_ledger_instance: Optional[RightsLedger] = None


def get_rights_ledger() -> RightsLedger:
    """获取权益账本全局实例"""
    global _ledger_instance
    if _ledger_instance is None:
        _ledger_instance = RightsLedger()
    return _ledger_instance
