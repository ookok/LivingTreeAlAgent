"""
税务引擎模块 - TaxEngine
=========================

核心功能：确保所有权益发放税务合规

税务策略：
- 采用"赠予"模式：由平台作为赠予方承担税款
- 不涉及用户个人所得税（用户获得的是税后权益）
- 税务透明，所有记录可审计

法律依据：
- 《个人所得税法》第二条：偶然所得，需缴纳个人所得税
- 但采用"赠予"模式时，赠予方承担税款，用户获得税后权益

Author: Hermes Desktop Team
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from decimal import Decimal, ROUND_DOWN
from datetime import datetime
import json
import uuid
import logging

logger = logging.getLogger(__name__)


class TaxStrategy:
    """税务策略配置"""

    # 中国主要税法规定
    TAX_RULES = {
        # 偶然所得
        'occasional_income': {
            'rate': Decimal('0.20'),            # 20%税率
            'threshold': Decimal('800.00'),      # 800元起征点
            'description': '个人得奖、中奖、中彩以及其他偶然性质的所得',
            'taxpayer': 'recipient',            # 所得人缴税
        },
        # 劳务报酬
        'labor_reward': {
            'rate': Decimal('0.20'),            # 20%税率
            'description': '个人独立从事各种技艺、提供各项劳务取得的报酬',
            'taxpayer': 'recipient',
        },
        # 赠予（企业对外捐赠）
        'donation': {
            'rate': Decimal('0.25'),            # 企业所得税率
            'description': '企业对外捐赠，赠予方承担相关税务',
            'taxpayer': 'donor',                # 赠予方缴税
        },
    }

    def __init__(self, strategy_type: str = 'donation'):
        """
        初始化税务策略

        Args:
            strategy_type: 'occasional_income' | 'donation'
        """
        self.strategy_type = strategy_type
        self.rule = self.TAX_RULES[strategy_type]

    @property
    def rate(self) -> Decimal:
        """获取税率"""
        return self.rule['rate']

    @property
    def taxpayer(self) -> str:
        """获取纳税人"""
        return self.rule['taxpayer']

    @property
    def description(self) -> str:
        """获取策略描述"""
        return self.rule['description']


@dataclass
class TaxRecord:
    """税务记录"""
    record_id: str
    period: str                          # 会计期间（如 2024-Q1）
    right_cost: Decimal                  # 权益成本
    tax_rate: Decimal                    # 税率
    tax_amount: Decimal                  # 税额
    total_cost: Decimal                  # 总成本（含税）
    taxpayer: str                        # 纳税人
    strategy: str                       # 税务策略
    created_at: datetime
    document_url: Optional[str] = None   # 税务文档URL

    def to_dict(self) -> Dict:
        return {
            'record_id': self.record_id,
            'period': self.period,
            'right_cost': float(self.right_cost),
            'tax_rate': float(self.tax_rate),
            'tax_amount': float(self.tax_amount),
            'total_cost': float(self.total_cost),
            'taxpayer': self.taxpayer,
            'strategy': self.strategy,
            'created_at': self.created_at.isoformat(),
            'document_url': self.document_url,
        }


class TaxEngine:
    """
    税务引擎 - 确保所有权益发放税务合规

    核心功能：
    1. 计算权益发放涉及的税款
    2. 生成税务申报文档
    3. 记录税务档案
    4. 提供税务审计接口
    """

    def __init__(self, strategy: TaxStrategy = None, db_path: str = "./data/tax_engine.db"):
        """
        初始化税务引擎

        Args:
            strategy: 税务策略，默认使用赠予策略
            db_path: 税务数据库路径
        """
        self.strategy = strategy or TaxStrategy('donation')
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """初始化税务数据库"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 税务记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tax_records (
                record_id TEXT PRIMARY KEY,
                period TEXT NOT NULL,
                right_cost REAL NOT NULL,
                tax_rate REAL NOT NULL,
                tax_amount REAL NOT NULL,
                total_cost REAL NOT NULL,
                taxpayer TEXT NOT NULL,
                strategy TEXT NOT NULL,
                created_at TEXT NOT NULL,
                document_url TEXT,
                batch_id TEXT
            )
        """)

        # 税务申报历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tax_filings (
                filing_id TEXT PRIMARY KEY,
                period TEXT NOT NULL,
                total_rights_cost REAL NOT NULL,
                total_tax_amount REAL NOT NULL,
                total_platform_cost REAL NOT NULL,
                grant_count INTEGER NOT NULL,
                filed_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                filing_document_url TEXT
            )
        """)

        conn.commit()
        conn.close()
        logger.info(f"税务引擎数据库初始化完成: {self.db_path}")

    def _get_connection(self):
        """获取数据库连接"""
        import sqlite3
        return sqlite3.connect(self.db_path)

    def calculate_tax(self, right_cost: float) -> Dict:
        """
        计算单个权益的税款

        Args:
            right_cost: 权益成本（平台成本）

        Returns:
            Dict: 税务计算结果
        """
        cost = Decimal(str(right_cost))
        rate = self.strategy.rate

        # 计算税额
        tax_amount = (cost * rate).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

        # 如果有起征点（如偶然所得800元起征）
        threshold = self.strategy.rule.get('threshold', Decimal('0'))
        if cost <= threshold:
            tax_amount = Decimal('0')

        return {
            'right_cost': float(cost),
            'tax_rate': float(rate),
            'tax_amount': float(tax_amount),
            'total_cost': float(cost + tax_amount),  # 平台总成本
            'taxpayer': self.strategy.taxpayer,
            'strategy': self.strategy.strategy_type,
            'threshold_applied': float(threshold) if threshold > 0 else None,
        }

    def calculate_batch_taxes(self, grants: List[Dict]) -> Dict:
        """
        批量计算税款

        Args:
            grants: 权益发放列表 [{right_id, right_cost, user_id, ...}, ...]

        Returns:
            Dict: 税务汇总信息
        """
        total_right_cost = Decimal('0')
        total_tax_amount = Decimal('0')
        total_platform_cost = Decimal('0')
        details = []

        for grant in grants:
            right_cost = Decimal(str(grant.get('right_cost', 0)))
            tax_info = self.calculate_tax(float(right_cost))

            total_right_cost += right_cost
            total_tax_amount += Decimal(str(tax_info['tax_amount']))
            total_platform_cost += Decimal(str(tax_info['total_cost']))

            details.append({
                'grant_id': grant.get('id', grant.get('right_id', '')),
                'user_id': grant.get('user_id', ''),
                'right_cost': tax_info['right_cost'],
                'tax_amount': tax_info['tax_amount'],
                'total_cost': tax_info['total_cost'],
            })

        return {
            'total_rights_cost': float(total_right_cost),
            'total_tax_amount': float(total_tax_amount),
            'total_platform_cost': float(total_platform_cost),
            'grant_count': len(grants),
            'details': details,
            'average_tax_rate': float(total_tax_amount / total_right_cost) if total_right_cost > 0 else 0,
        }

    def generate_tax_document(self, period: str, batch_id: str = None) -> Dict:
        """
        生成税务申报文档

        Args:
            period: 会计期间
            batch_id: 批次ID

        Returns:
            Dict: 税务文档
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 查询该期间的税务记录
        cursor.execute("""
            SELECT record_id, period, right_cost, tax_rate, tax_amount, total_cost
            FROM tax_records
            WHERE period = ? AND batch_id = ?
        """, (period, batch_id))

        rows = cursor.fetchall()
        conn.close()

        total_rights = Decimal('0')
        total_tax = Decimal('0')
        total_cost = Decimal('0')

        for row in rows:
            total_rights += Decimal(str(row[2]))
            total_tax += Decimal(str(row[4]))
            total_cost += Decimal(str(row[5]))

        # 生成文档
        document = {
            'document_id': f"tax_doc_{uuid.uuid4().hex[:12]}",
            'period': period,
            'batch_id': batch_id,
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_rights_cost': float(total_rights),
                'total_tax_amount': float(total_tax),
                'total_platform_cost': float(total_cost),
                'record_count': len(rows),
            },
            'strategy': {
                'type': self.strategy.strategy_type,
                'rate': float(self.strategy.rate),
                'taxpayer': self.strategy.taxpayer,
                'description': self.strategy.description,
            },
            'disclaimer': '本税务文档仅供参考，不构成税务申报依据。具体税务申报请咨询专业税务顾问。',
        }

        logger.info(f"税务文档生成: period={period}, total_tax={total_tax}")
        return document

    async def record_taxes(self, period: str, grants: List[Dict], batch_id: str = None) -> List[str]:
        """
        记录税款（持久化到数据库）

        Args:
            period: 会计期间
            grants: 权益发放列表
            batch_id: 批次ID

        Returns:
            List[str]: 税务记录ID列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        record_ids = []

        for grant in grants:
            tax_info = self.calculate_tax(grant.get('right_cost', 0))

            record_id = f"tax_{uuid.uuid4().hex[:12]}"
            record_ids.append(record_id)

            cursor.execute("""
                INSERT INTO tax_records
                (record_id, period, right_cost, tax_rate, tax_amount, total_cost,
                 taxpayer, strategy, created_at, batch_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record_id,
                period,
                tax_info['right_cost'],
                tax_info['tax_rate'],
                tax_info['tax_amount'],
                tax_info['total_cost'],
                tax_info['taxpayer'],
                tax_info['strategy'],
                datetime.now().isoformat(),
                batch_id,
            ))

        conn.commit()
        conn.close()

        logger.info(f"税务记录已保存: period={period}, count={len(record_ids)}")
        return record_ids

    async def get_tax_summary(self, start_period: str = None, end_period: str = None) -> Dict:
        """
        获取税务汇总

        Args:
            start_period: 开始期间
            end_period: 结束期间

        Returns:
            Dict: 税务汇总
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if start_period and end_period:
            cursor.execute("""
                SELECT period,
                       SUM(right_cost) as total_rights,
                       SUM(tax_amount) as total_tax,
                       SUM(total_cost) as total_cost,
                       COUNT(*) as record_count
                FROM tax_records
                WHERE period >= ? AND period <= ?
                GROUP BY period
                ORDER BY period DESC
            """, (start_period, end_period))
        else:
            cursor.execute("""
                SELECT period,
                       SUM(right_cost) as total_rights,
                       SUM(tax_amount) as total_tax,
                       SUM(total_cost) as total_cost,
                       COUNT(*) as record_count
                FROM tax_records
                GROUP BY period
                ORDER BY period DESC
            """)

        rows = cursor.fetchall()
        conn.close()

        summary = {
            'total_rights_cost': 0.0,
            'total_tax_amount': 0.0,
            'total_platform_cost': 0.0,
            'total_records': 0,
            'by_period': [],
        }

        for row in rows:
            period_data = {
                'period': row[0],
                'total_rights_cost': float(row[1] or 0),
                'total_tax_amount': float(row[2] or 0),
                'total_platform_cost': float(row[3] or 0),
                'record_count': row[4],
            }
            summary['by_period'].append(period_data)

            summary['total_rights_cost'] += period_data['total_rights_cost']
            summary['total_tax_amount'] += period_data['total_tax_amount']
            summary['total_platform_cost'] += period_data['total_platform_cost']
            summary['total_records'] += row[4]

        return summary

    def get_tax_info_for_right(self, right_cost: float) -> Dict:
        """
        获取权益税务信息（供UI展示）

        Returns:
            Dict: 税务信息
        """
        tax = self.calculate_tax(right_cost)
        return {
            '展示信息': {
                '权益成本': f"¥{tax['right_cost']:.2f}",
                '税率': f"{tax['tax_rate']*100:.1f}%",
                '税额': f"¥{tax['tax_amount']:.2f}",
                '平台总成本': f"¥{tax['total_cost']:.2f}",
            },
            '税务说明': {
                '纳税主体': '平台（赠予方）',
                '策略类型': '赠予',
                '用户获得': '税后权益',
                '用户税务责任': '无',
            },
            '合规提示': '根据中国税法，平台作为赠予方承担相关税款，用户获得的是税后权益，无需额外缴税。'
        }


# 全局单例
_tax_engine_instance: Optional[TaxEngine] = None


def get_tax_engine() -> TaxEngine:
    """获取税务引擎全局实例"""
    global _tax_engine_instance
    if _tax_engine_instance is None:
        _tax_engine_instance = TaxEngine()
    return _tax_engine_instance
