"""
林窗视图 (Canopy Vista)

透过树冠看世界的沉浸式界面

包含:
- 林窗控制台 (Canopy Console) - 主界面
- 智慧林冠图 (Intelligent Canopy Map) - 时空引力场可视化
- 林间贸易台 (Forest Trade Deck) - 商品全息投影
- 信使叶灵核 (Leaf Messenger Core) - AI全息投影
- 脉动通讯阵 (Sap Comm Array) - 网络可视化
- 导航年轮 (Navigation Ring) - 导航球
- 晨露声音 (Morning Dew Sounds) - 声音引擎
- 生命样式 (Living Styles) - 全息样式
"""

from .bridge_styles import (
    HolographicColors,
    HolographicFonts,
    HolographicPainter,
    HolographicPulseEffect,
    HolographicGlowAnimation,
    get_bridge_stylesheet,
    create_holo_card_style,
    NAV_SPHERE_STYLESHEET,
)

from .bridge_console import (
    BridgeConsole,
    get_bridge_console,
    create_bridge_console,
)

from .holographic_star_map import (
    HolographicNode,
    GravityLine,
    HolographicStarMapScene,
    HolographicStarMap,
)

from .trade_deck import (
    HolographicProductItem,
    MatterReorganizer,
    MatchingRadar,
    TradeDeck,
)

from .oracle_core import (
    AIHologram,
    AIBubble,
    OracleCoreWidget,
    OracleCore,
    get_oracle_core,
)

from .comm_array import (
    WarpBeacon,
    P2PLinkVisualizer,
    CommArrayWidget,
    CommArray,
    get_comm_array,
)

from .navigation_sphere import (
    NavigationSphere,
)

from .sound_engine import (
    SoundEngine,
    SoundEffects,
    NarrativeLines,
    get_sound_engine,
    create_sound_engine,
)


__version__ = "1.0.0"
__author__ = "Hermes Desktop Team"

__all__ = [
    # 样式
    "HolographicColors",
    "HolographicFonts",
    "HolographicPainter",
    "HolographicPulseEffect",
    "HolographicGlowAnimation",
    "get_bridge_stylesheet",
    "create_holo_card_style",
    "NAV_SPHERE_STYLESHEET",

    # 核心
    "BridgeConsole",
    "get_bridge_console",
    "create_bridge_console",

    # 星图
    "HolographicNode",
    "GravityLine",
    "HolographicStarMapScene",
    "HolographicStarMap",

    # 贸易
    "HolographicProductItem",
    "MatterReorganizer",
    "MatchingRadar",
    "TradeDeck",

    # AI
    "AIHologram",
    "AIBubble",
    "OracleCoreWidget",
    "OracleCore",
    "get_oracle_core",

    # 通讯
    "WarpBeacon",
    "P2PLinkVisualizer",
    "CommArrayWidget",
    "CommArray",
    "get_comm_array",

    # 导航
    "NavigationSphere",

    # 声音
    "SoundEngine",
    "SoundEffects",
    "NarrativeLines",
    "get_sound_engine",
    "create_sound_engine",
]