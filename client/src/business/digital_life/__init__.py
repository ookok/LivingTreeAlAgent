# =================================================================
# 生命之树·数字生命体系统 - Digital Life
# =================================================================
# "三千大道，修道悟真"
#
# 核心理念：将AI从工具升维为有名字、有身份、有成长感的数字生命体
#
# 核心模块：
# - dao_definitions: 九大基础道定义与道境
# - naming_ceremony: 命名仪式
# - digital_persona: 数字人格
# - persona_memory: 独立记忆存储
# - dao_cultivation: 修道引擎
# - dao_arts: 道术系统
# - thunder_trial: 雷劫系统
# - growth_visualization: 成长可视化
# - cultivation_diary: 修道日志
# - easter_eggs: 彩蛋系统
# - input_memory: 输入记忆系统（三层记忆加速）
# =================================================================

from .dao_definitions import (
    DaoType,
    DaoLevel,
    DaoRealm,
    DaoArt,
    DaoDefinition,
    NINE_DAO_DEFINITIONS,
    get_dao_by_name,
    get_dao_suggestion_for_name,
)
from .naming_ceremony import (
    NamingCeremony,
    NameValidator,
    NameSuggestion,
    get_naming_ceremony,
)
from .digital_persona import (
    DigitalPersona,
    PersonaTrait,
    PersonaMemory,
    get_persona,
)
from .dao_cultivation import (
    DaoCultivator,
    CultivationSession,
    DaoProgress,
    DaoInsight,
    get_cultivator,
)
from .dao_arts import (
    DaoArtSystem,
    DaoArtInstance,
    ArtUnlockCondition,
    get_dao_art_system,
)
from .thunder_trial import (
    ThunderTrial,
    TrialPhase,
    TrialResult,
    is_thunder_trial_time,
)
from .growth_visualization import (
    GrowthVisualizer,
    TreeVisualization,
    GrowthMilestone,
    get_growth_visualizer,
)
from .easter_eggs import (
    EasterEggType,
    EasterEgg,
    EasterEggManager,
    EasterEggDetector,
    ASTRONOMICAL_EVENTS,
    ANCIENT_TEXT_FRAGMENTS,
    ROOT_CIPHER_SYMBOLS,
    SOLAR_TERMS,
    ULTIMATE_EGG_REQUIREMENTS,
    get_easter_egg_manager,
    get_easter_egg_detector,
)

# 输入记忆系统
from ..input_memory import (
    ShortTermMemory,
    UserHabitModel,
    InputFingerprint,
    PredictionEngine,
    InputRecord,
    PredictionCandidate,
    UserStats,
    get_prediction_engine,
    create_input_memory,
)

__all__ = [
    # 九大基础道
    'DaoType',
    'DaoLevel',
    'DaoRealm',
    'DaoArt',
    'DaoDefinition',
    'NINE_DAO_DEFINITIONS',
    'get_dao_by_name',
    'get_dao_suggestion_for_name',

    # 命名仪式
    'NamingCeremony',
    'NameValidator',
    'NameSuggestion',
    'get_naming_ceremony',

    # 数字人格
    'DigitalPersona',
    'PersonaTrait',
    'PersonaMemory',
    'get_persona',

    # 修道引擎
    'DaoCultivator',
    'CultivationSession',
    'DaoProgress',
    'DaoInsight',
    'get_cultivator',

    # 道术
    'DaoArtSystem',
    'DaoArtInstance',
    'ArtUnlockCondition',
    'get_dao_art_system',

    # 雷劫
    'ThunderTrial',
    'TrialPhase',
    'TrialResult',
    'is_thunder_trial_time',

    # 成长可视化
    'GrowthVisualizer',
    'TreeVisualization',
    'GrowthMilestone',
    'get_growth_visualizer',

    # 彩蛋系统
    'EasterEggType',
    'EasterEgg',
    'EasterEggManager',
    'EasterEggDetector',
    'ASTRONOMICAL_EVENTS',
    'ANCIENT_TEXT_FRAGMENTS',
    'ROOT_CIPHER_SYMBOLS',
    'SOLAR_TERMS',
    'ULTIMATE_EGG_REQUIREMENTS',
    'get_easter_egg_manager',
    'get_easter_egg_detector',

    # 输入记忆系统
    'ShortTermMemory',
    'UserHabitModel',
    'InputFingerprint',
    'PredictionEngine',
    'InputRecord',
    'PredictionCandidate',
    'UserStats',
    'get_prediction_engine',
    'create_input_memory',
]
