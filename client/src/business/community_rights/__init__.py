"""
社区共建者权益计划 - CommunityRights
=======================================

核心理念：把"钱"彻底从系统中剥离，只流通"权益"，由平台承担所有税务责任。

设计原则：
1. 积分永不兑现现金
2. 收益转化为"社区发展基金"
3. 去金融化：不承诺、不预期、不负债
4. 税务清晰：平台承担所有税务责任

模块组成：
- rights_ledger: 权益账本 - 记录所有用户权益
- tax_engine: 税务引擎 - 确保税务合规
- community_fund: 社区发展基金 - 盈利回馈核心
- manager: 统一管理器 - 整合三大模块

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
from .manager import (
    CommunityRightsManager,
    get_community_rights_manager,
)

__all__ = [
    # 版本信息
    '__version__',
    '__author__': 'Hermes Desktop Team',
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
    # Manager
    'CommunityRightsManager',
    'get_community_rights_manager',
]
