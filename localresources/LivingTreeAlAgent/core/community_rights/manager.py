"""
社区权益系统 - 集成模块
=========================

整合 RightsLedger、CommunityFund、TaxEngine 为统一系统

Author: Hermes Desktop Team
"""

from .rights_ledger import (
    RightsLedger,
    DigitalRight,
    RightType,
    RightSource,
    RightDefinition,
    get_rights_ledger,
)
from .tax_engine import (
    TaxEngine,
    TaxStrategy,
    TaxRecord,
    get_tax_engine,
)
from .community_fund import (
    CommunityFund,
    AllocationRule,
    DistributionPlan,
    FundStatement,
    get_community_fund,
)

__all__ = [
    # RightsLedger
    'RightsLedger',
    'DigitalRight',
    'RightType',
    'RightSource',
    'RightDefinition',
    'get_rights_ledger',
    # TaxEngine
    'TaxEngine',
    'TaxStrategy',
    'TaxRecord',
    'get_tax_engine',
    # CommunityFund
    'CommunityFund',
    'AllocationRule',
    'DistributionPlan',
    'FundStatement',
    'get_community_fund',
]


class CommunityRightsManager:
    """
    社区权益统一管理器

    整合三大模块，提供统一接口
    """

    def __init__(self):
        self.ledger = get_rights_ledger()
        self.tax_engine = get_tax_engine()
        self.fund = get_community_fund(self.ledger, self.tax_engine)

    async def get_user_rights(self, user_id: str, include_expired: bool = False) -> list:
        """获取用户所有权益"""
        return await self.ledger.get_user_rights(user_id, include_expired)

    async def get_user_rights_summary(self, user_id: str) -> dict:
        """获取用户权益摘要"""
        return await self.ledger.get_user_rights_summary(user_id)

    async def grant_right_to_user(self, user_id: str, right_type_id: str) -> dict:
        """
        向用户发放权益

        Args:
            user_id: 用户ID
            right_type_id: 权益类型ID

        Returns:
            dict: 发放结果
        """
        # 计算税务
        tax_info = self.tax_engine.calculate_tax(
            self.ledger.BUILTIN_RIGHTS[right_type_id].cost_to_platform
        )

        # 发放权益
        right = await self.ledger.grant_right_by_type(
            user_id=user_id,
            right_type_id=right_type_id,
            source=RightSource.COMMUNITY_FUND,
            tax_info=tax_info,
        )

        if right:
            # 记录税务
            await self.tax_engine.record_taxes(
                period=self._get_current_period(),
                grants=[{
                    'right_id': right.id,
                    'user_id': user_id,
                    'right_cost': right.cost_to_platform,
                }],
            )

            return {
                'success': True,
                'right': right.to_dict(),
                'tax_info': tax_info,
            }

        return {'success': False, 'error': '权益发放失败'}

    async def distribute_profit(self, amount: float, period: str = None) -> dict:
        """
        分配平台盈利到社区基金

        Args:
            amount: 盈利金额（税后净利润）
            period: 会计期间

        Returns:
            dict: 分配结果
        """
        period = period or self._get_current_period()

        # 接收盈利并分配
        allocation_result = await self.fund.receive_profit(amount, period)

        return allocation_result

    async def execute_distribution_plan(self, period: str = None) -> dict:
        """
        执行用户权益分配

        Args:
            period: 会计期间

        Returns:
            dict: 执行结果
        """
        period = period or self._get_current_period()

        # 创建分配计划
        plan = await self.fund.plan_distribution(period)

        if not plan:
            return {'success': False, 'error': '无可分配的基金或贡献'}

        # 执行计划
        result = await self.fund.execute_distribution(plan)

        return {
            'success': True,
            'plan': plan.to_dict(),
            'result': result,
        }

    async def get_fund_statement(self, period: str) -> dict:
        """获取基金报告"""
        statement = await self.fund.get_period_statement(period)
        if statement:
            return statement.to_dict()
        return None

    def get_right_definitions(self) -> list:
        """获取所有权益定义"""
        return self.ledger.get_all_rights_for_display()

    def get_tax_preview(self, right_type_id: str) -> dict:
        """
        预览权益税务信息

        Args:
            right_type_id: 权益类型ID

        Returns:
            dict: 税务预览
        """
        definition = self.ledger.BUILTIN_RIGHTS.get(right_type_id)
        if not definition:
            return None

        return self.tax_engine.get_tax_info_for_right(definition.cost_to_platform)

    def get_disclaimer(self) -> str:
        """获取免责声明"""
        return self.fund.get_disclaimer()

    def _get_current_period(self) -> str:
        """获取当前会计期间"""
        now = datetime.now()
        quarter = (now.month - 1) // 3 + 1
        return f"{now.year}-Q{quarter}"

    async def get_all_rights_for_user(self, user_id: str) -> dict:
        """
        获取用户所有权益（兼容旧接口）

        Returns:
            dict: 用户权益信息
        """
        rights = await self.get_user_rights(user_id)
        summary = await self.get_user_rights_summary(user_id)

        return {
            'rights': [r.to_dict() for r in rights],
            'summary': summary,
            'definitions': self.get_right_definitions(),
            'disclaimer': self.get_disclaimer(),
        }


# 全局管理器实例
_manager_instance: CommunityRightsManager = None


def get_community_rights_manager() -> CommunityRightsManager:
    """获取社区权益统一管理器"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = CommunityRightsManager()
    return _manager_instance
