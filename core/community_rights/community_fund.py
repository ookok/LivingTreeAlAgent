"""
社区发展基金模块 - CommunityFund
==================================

核心功能：将平台盈利转化为用户权益回馈

设计原则：
1. 积分永不兑现现金
2. 收益转化为"社区发展基金"
3. 去金融化：不承诺、不预期、不负债
4. 税务清晰：平台承担所有税务责任

分配规则：
- 50% 用于用户回馈
- 30% 用于平台发展
- 20% 用于运营储备

Author: Hermes Desktop Team
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, date
import json
import uuid
import logging

logger = logging.getLogger(__name__)


@dataclass
class AllocationRule:
    """分配规则"""
    purpose: str                          # 用途
    ratio: Decimal                       # 分配比例
    description: str                      # 描述


@dataclass
class DistributionPlan:
    """分配计划"""
    plan_id: str
    period: str                          # 会计期间
    total_fund: Decimal                  # 总基金
    allocations: Dict[str, Decimal]      # 分配明细
    user_distribution: List[Dict]        # 用户分配明细
    tax_info: Dict                       # 税务信息
    created_at: datetime
    status: str = 'pending'              # pending / executed / cancelled

    def to_dict(self) -> Dict:
        return {
            'plan_id': self.plan_id,
            'period': self.period,
            'total_fund': float(self.total_fund),
            'allocations': {k: float(v) for k, v in self.allocations.items()},
            'user_distribution': self.user_distribution,
            'tax_info': self.tax_info,
            'created_at': self.created_at.isoformat(),
            'status': self.status,
        }


@dataclass
class FundStatement:
    """社区基金报告"""
    period: str
    total_profit: Decimal
    allocation: Dict[str, Decimal]
    distribution_summary: Dict
    tax_paid: Decimal
    total_platform_cost: Decimal
    generated_at: datetime
    disclaimer: str = "本回馈为平台赠予的数字权益，不构成任何投资回报承诺。"

    def to_dict(self) -> Dict:
        return {
            'period': self.period,
            'total_profit': float(self.total_profit),
            'allocation': {k: float(v) for k, v in self.allocation.items()},
            'distribution_summary': self.distribution_summary,
            'tax_paid': float(self.tax_paid),
            'total_platform_cost': float(self.total_platform_cost),
            'generated_at': self.generated_at.isoformat(),
            'disclaimer': self.disclaimer,
        }


class CommunityFund:
    """
    社区发展基金 - 盈利回馈的核心

    核心功能：
    1. 接收平台盈利并分配到不同用途
    2. 计算用户贡献并分配权益
    3. 生成透明化基金报告
    4. 与税务引擎集成确保合规
    """

    # 默认分配规则
    DEFAULT_ALLOCATION_RULES = [
        AllocationRule(
            purpose='user_rewards',
            ratio=Decimal('0.50'),      # 50%用于用户回馈
            description='根据用户贡献分配数字权益'
        ),
        AllocationRule(
            purpose='platform_development',
            ratio=Decimal('0.30'),     # 30%平台发展
            description='用于平台功能研发和基础设施'
        ),
        AllocationRule(
            purpose='operational_reserve',
            ratio=Decimal('0.20'),     # 20%运营储备
            description='用于应对突发情况和未来发展'
        ),
    ]

    def __init__(self, rights_ledger, tax_engine, db_path: str = "./data/community_fund.db"):
        """
        初始化社区发展基金

        Args:
            rights_ledger: 权益账本实例
            tax_engine: 税务引擎实例
            db_path: 数据库路径
        """
        self.rights_ledger = rights_ledger
        self.tax_engine = tax_engine
        self.db_path = db_path
        self.allocation_rules = self.DEFAULT_ALLOCATION_RULES.copy()
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 基金账户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fund_accounts (
                account_id TEXT PRIMARY KEY,
                purpose TEXT NOT NULL UNIQUE,
                balance REAL DEFAULT 0.0,
                total_inflow REAL DEFAULT 0.0,
                total_outflow REAL DEFAULT 0.0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 分配记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS allocation_records (
                record_id TEXT PRIMARY KEY,
                period TEXT NOT NULL,
                profit_amount REAL NOT NULL,
                allocations TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 分配计划表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS distribution_plans (
                plan_id TEXT PRIMARY KEY,
                period TEXT NOT NULL,
                total_fund REAL NOT NULL,
                user_distribution TEXT NOT NULL,
                tax_info TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending'
            )
        """)

        # 用户贡献记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_contributions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                period TEXT NOT NULL,
                credit_score REAL NOT NULL,
                contribution_type TEXT,
                details TEXT,
                recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()
        logger.info(f"社区基金数据库初始化完成: {self.db_path}")

    def _get_connection(self):
        """获取数据库连接"""
        import sqlite3
        return sqlite3.connect(self.db_path)

    async def receive_profit(self, amount: float, period: str, source: str = 'platform') -> Dict:
        """
        接收平台盈利

        Args:
            amount: 盈利金额（税后净利润）
            period: 会计期间（如 '2024-Q1'）
            source: 盈利来源

        Returns:
            Dict: 分配结果
        """
        profit = Decimal(str(amount))
        allocations = {}

        conn = self._get_connection()
        cursor = conn.cursor()

        for rule in self.allocation_rules:
            allocated_amount = (profit * rule.ratio).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
            allocations[rule.purpose] = allocated_amount

            # 更新账户余额
            cursor.execute("""
                INSERT INTO fund_accounts (account_id, purpose, balance, total_inflow)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(purpose) DO UPDATE SET
                    balance = balance + excluded.balance,
                    total_inflow = total_inflow + excluded.total_inflow,
                    updated_at = CURRENT_TIMESTAMP
            """, (rule.purpose, rule.purpose, float(allocated_amount), float(allocated_amount)))

        # 记录分配
        cursor.execute("""
            INSERT INTO allocation_records (record_id, period, profit_amount, allocations)
            VALUES (?, ?, ?, ?)
        """, (f"alloc_{uuid.uuid4().hex[:12]}", period, float(profit), json.dumps({k: float(v) for k, v in allocations.items()})))

        conn.commit()
        conn.close()

        logger.info(f"盈利已接收并分配: period={period}, amount={amount}, allocations={allocations}")

        return {
            'period': period,
            'profit_received': float(profit),
            'allocations': {k: float(v) for k, v in allocations.items()},
            'allocation_rules': [
                {'purpose': r.purpose, 'ratio': float(r.ratio), 'description': r.description}
                for r in self.allocation_rules
            ],
        }

    async def get_user_contributions(self, period: str = None) -> Dict[str, Decimal]:
        """
        获取用户贡献分数

        在实际系统中，这里应该从 credit_economy 模块获取用户的真实贡献分数。
        目前使用模拟数据作为示例。

        Args:
            period: 会计期间

        Returns:
            Dict: user_id -> 贡献分数
        """
        # TODO: 接入真实的用户贡献系统
        # 目前返回模拟数据
        mock_contributions = {
            'user_001': Decimal('1500'),  # 高贡献用户
            'user_002': Decimal('800'),
            'user_003': Decimal('2000'),  # 最高贡献
            'user_004': Decimal('500'),
            'user_005': Decimal('1200'),
        }
        return mock_contributions

    async def plan_distribution(self, period: str) -> DistributionPlan:
        """
        规划用户权益分配

        Args:
            period: 会计期间

        Returns:
            DistributionPlan: 分配计划
        """
        # 获取用户回馈账户余额
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT balance FROM fund_accounts WHERE purpose = 'user_rewards'
        """)
        row = cursor.fetchone()
        conn.close()

        if not row or row[0] <= 0:
            logger.warning(f"用户回馈账户余额为0，无法分配: period={period}")
            return None

        available_fund = Decimal(str(row[0]))

        # 获取用户贡献
        user_credits = await self.get_user_contributions(period)
        total_credits = sum(user_credits.values())

        if total_credits == 0:
            logger.warning(f"用户总贡献为0，无法分配: period={period}")
            return None

        # 计算用户权益分配
        user_distribution = []
        for user_id, credits in user_credits.items():
            weight = credits / total_credits
            user_share = (available_fund * Decimal(str(weight))).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

            # 根据份额选择权益
            rights_plan = self._select_rights_for_budget(user_share)

            user_distribution.append({
                'user_id': user_id,
                'credits': float(credits),
                'weight': float(weight),
                'fund_share': float(user_share),
                'rights_plan': rights_plan,
            })

        # 计算税务
        total_rights_cost = sum(
            sum(r['unit_cost'] * r['quantity'] for r in u['rights_plan'])
            for u in user_distribution
        )
        tax_info = self.tax_engine.calculate_batch_taxes([
            {'right_cost': total_rights_cost / len(user_distribution)}
            for _ in user_distribution
        ])

        # 创建分配计划
        plan = DistributionPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:12]}",
            period=period,
            total_fund=available_fund,
            allocations={'user_rewards': available_fund},
            user_distribution=user_distribution,
            tax_info=tax_info,
            created_at=datetime.now(),
            status='pending',
        )

        logger.info(f"分配计划已创建: plan_id={plan.plan_id}, period={period}, total_fund={available_fund}")
        return plan

    def _select_rights_for_budget(self, budget: Decimal) -> List[Dict]:
        """
        根据预算选择权益组合

        Args:
            budget: 用户可用的预算

        Returns:
            List[Dict]: 权益计划
        """
        from .rights_ledger import RightsLedger

        rights_plan = []
        remaining_budget = budget

        # 按成本排序权益（优先高性价比）
        sorted_rights = sorted(
            RightsLedger.BUILTIN_RIGHTS.items(),
            key=lambda x: x[1].cost_to_platform
        )

        for right_id, definition in sorted_rights:
            if remaining_budget < Decimal(str(definition.cost_to_platform)):
                continue

            if definition.cost_to_platform == 0:
                # 零成本权益直接发放
                rights_plan.append({
                    'right_id': right_id,
                    'name': definition.name,
                    'quantity': 1,
                    'unit_cost': 0.0,
                })
            else:
                max_count = int(remaining_budget / Decimal(str(definition.cost_to_platform)))
                if max_count > 0 and definition.max_issue_per_user > 0:
                    quantity = min(1, max_count, definition.max_issue_per_user)
                    rights_plan.append({
                        'right_id': right_id,
                        'name': definition.name,
                        'quantity': quantity,
                        'unit_cost': definition.cost_to_platform,
                    })
                    remaining_budget -= Decimal(str(definition.cost_to_platform * quantity))

        return rights_plan

    async def execute_distribution(self, plan: DistributionPlan) -> Dict:
        """
        执行分配计划

        Args:
            plan: 分配计划

        Returns:
            Dict: 执行结果
        """
        if plan.status != 'pending':
            return {'success': False, 'error': '计划已执行或已取消'}

        from .rights_ledger import RightSource

        results = {
            'success': True,
            'plan_id': plan.plan_id,
            'users_granted': 0,
            'rights_granted': 0,
            'errors': [],
        }

        # 批量发放权益
        grants = []
        for user_plan in plan.user_distribution:
            user_id = user_plan['user_id']
            for right_item in user_plan['rights_plan']:
                grants.append({
                    'user_id': user_id,
                    'right_type_id': right_item['right_id'],
                    'source': RightSource.COMMUNITY_FUND,
                    'tax_info': None,  # 税务已在计划阶段计算
                })

        # 调用权益账本批量发放
        grant_results = await self.rights_ledger.batch_grant_rights(grants)

        for user_id, success in grant_results.items():
            if success:
                results['users_granted'] += 1
                user_rights = sum(1 for g in grants if g['user_id'] == user_id)
                results['rights_granted'] += user_rights
            else:
                results['errors'].append(f"用户 {user_id} 权益发放失败")

        # 更新计划状态
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE distribution_plans SET status = 'executed' WHERE plan_id = ?
        """, (plan.plan_id,))

        # 扣除账户余额
        cursor.execute("""
            UPDATE fund_accounts
            SET balance = balance - ?, updated_at = CURRENT_TIMESTAMP
            WHERE purpose = 'user_rewards'
        """, (float(plan.total_fund),))

        conn.commit()
        conn.close()

        # 记录税务
        period = plan.period
        await self.tax_engine.record_taxes(period, grants, plan.plan_id)

        plan.status = 'executed'
        logger.info(f"分配计划执行完成: plan_id={plan.plan_id}, users={results['users_granted']}")

        return results

    async def get_period_statement(self, period: str) -> FundStatement:
        """
        获取指定期间的基金报告

        Args:
            period: 会计期间

        Returns:
            FundStatement: 基金报告
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 获取分配记录
        cursor.execute("""
            SELECT profit_amount, allocations FROM allocation_records
            WHERE period = ?
        """, (period,))
        row = cursor.fetchone()

        if not row:
            return None

        total_profit = Decimal(str(row[0]))
        allocations = json.loads(row[1])

        # 获取税务信息
        tax_summary = await self.tax_engine.get_tax_summary(start_period=period, end_period=period)

        # 获取分配摘要
        cursor.execute("""
            SELECT user_id, fund_share FROM distribution_plans p,
                   json_each(p.user_distribution)
            WHERE p.period = ? AND p.status = 'executed'
        """, (period,))

        distribution_rows = cursor.fetchall()
        conn.close()

        distribution_summary = {
            'total_users': len(distribution_rows),
            'total_distributed': sum(row[1] for row in distribution_rows) if distribution_rows else 0,
        }

        return FundStatement(
            period=period,
            total_profit=total_profit,
            allocation={k: Decimal(str(v)) for k, v in allocations.items()},
            distribution_summary=distribution_summary,
            tax_paid=Decimal(str(tax_summary.get('total_tax_amount', 0))),
            total_platform_cost=Decimal(str(tax_summary.get('total_platform_cost', 0))),
            generated_at=datetime.now(),
        )

    async def get_fund_status(self) -> Dict:
        """
        获取基金状态

        Returns:
            Dict: 基金状态
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT purpose, balance, total_inflow, total_outflow
            FROM fund_accounts
        """)

        rows = cursor.fetchall()
        conn.close()

        accounts = {}
        for row in rows:
            accounts[row[0]] = {
                'balance': float(row[1]),
                'total_inflow': float(row[2]),
                'total_outflow': float(row[3]),
            }

        return {
            'accounts': accounts,
            'allocation_rules': [
                {'purpose': r.purpose, 'ratio': float(r.ratio), 'description': r.description}
                for r in self.allocation_rules
            ],
            'updated_at': datetime.now().isoformat(),
        }

    def get_disclaimer(self) -> str:
        """获取免责声明"""
        return (
            "【重要声明】\n"
            "1. 本平台所有用户回馈均为数字权益赠予，不涉及现金支付。\n"
            "2. 本回馈不构成任何投资回报承诺，平台不保证定期或必然发放。\n"
            "3. 积分和权益不可转让、不可交易、不可变现。\n"
            "4. 平台赠予权益涉及的相关税款，由平台依法承担并缴纳。\n"
            "5. 平台保留对积分规则和权益发放的最终解释权及修改权。"
        )


# 全局单例
_fund_instance: Optional[CommunityFund] = None


def get_community_fund(rights_ledger=None, tax_engine=None) -> CommunityFund:
    """获取社区发展基金全局实例"""
    global _fund_instance
    if _fund_instance is None:
        if rights_ledger is None:
            from .rights_ledger import get_rights_ledger
            rights_ledger = get_rights_ledger()
        if tax_engine is None:
            from .tax_engine import get_tax_engine
            tax_engine = get_tax_engine()
        _fund_instance = CommunityFund(rights_ledger, tax_engine)
    return _fund_instance
