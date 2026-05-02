"""
环保全生命周期智能体系统 - Environmental Lifecycle Intelligence System (ELIS)
==========================================================================

核心理念：从"合规成本"到"竞争资产"的环保数字护照

七阶段闭环：
环评(EIA) → 建设(Construction) → 竣工验收(Acceptance) →
排污许可(Permit) → 运营(Operation) → 应急(Emergency) → 退役(Decommission)

最终目标：L5级环保自动驾驶
"""

from .env_lifecycle_manager import (
    EnvLifecycleManager,
    LifecycleStage,
    LifecycleStatus,
    EnvPassport,
    ProjectRecord
)

from .eia_40 import EIA40Engine
from .construction_supervision import ConstructionSupervisionEngine
from .acceptance_engine import AcceptanceEngine
from .permit管家 import PermitIntelligenceEngine
from .emergency_engine import EmergencyIntelligenceEngine
from .risk_management import RiskManagementEngine
from .decommission_engine import DecommissionEngine
from .data_lake import EnvDataLake
from .model_library import ModelLibrary

__all__ = [
    # 核心管理器
    'EnvLifecycleManager',
    'LifecycleStage',
    'LifecycleStatus',
    'EnvPassport',
    'ProjectRecord',

    # 七大引擎
    'EIA40Engine',                    # 模块1: 智能环评4.0
    'ConstructionSupervisionEngine', # 模块2: 建设期监理
    'AcceptanceEngine',              # 模块3: 竣工验收
    'PermitIntelligenceEngine',      # 模块4: 排污许可管家
    'EmergencyIntelligenceEngine',   # 模块5: 应急预案
    'RiskManagementEngine',          # 模块6: 风险管理
    'DecommissionEngine',            # 模块7: 退役管理

    # 数据与模型
    'EnvDataLake',
    'ModelLibrary',
]

# 自动驾驶等级定义
AUTOPILOT_LEVELS = {
    'L1': '辅助生成报告 - 人工审核',
    'L2': '半自动化 - AI生成+人工确认',
    'L3': '条件自动化 - AI主导+人工监督',
    'L4': '高度自动化 - AI决策+自动执行',
    'L5': '完全自动化 - 全流程无人干预',
}

# 生命周期阶段
LIFECYCLE_STAGES = {
    'EIA': '环境影响评价',
    'CONSTRUCTION': '建设期监理',
    'ACCEPTANCE': '竣工环保验收',
    'PERMIT': '排污许可管理',
    'OPERATION': '运营期监管',
    'EMERGENCY': '环境应急响应',
    'DECOMMISSION': '退役期管理',
}

__version__ = '1.0.0'
