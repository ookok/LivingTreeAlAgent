"""
生命之树 (Living Tree)

核心理念：用生长语言重塑技术模块，让代码散发温润的生命气息。

🌳 顶层架构 - 生命主干 (The Trunk)
🍃 智能与进化 - 智慧树芯 (The Heartwood)
🌐 网络与通信 - 根系网络 (The Root Network)
📧 邮箱与消息 - 脉动信囊 (Sap Channel)
🛒 时空引力电商 - 林间集市 (Forest Bazaar)
🛠️ 工具与装配 - 根系装配园 (Root Assembly Garden)
🎨 UI与交互 - 林窗视图 (Canopy Vista)
"""

from .living_tree_naming import (
    get_living_name,
    get_narrative,
    format_tech_with_living,
    NARRATIVE_LINES,
    TRUNK_NAMING,
    HEARTWOOD_NAMING,
    ROOT_NETWORK_NAMING,
    SAP_CHANNEL_NAMING,
    FOREST_BAZAAR_NAMING,
    ASSEMBLY_GARDEN_NAMING,
    CANOPY_VISTA_NAMING,
)


__all__ = [
    'get_living_name',           # 获取术语的生命之树命名
    'get_narrative',              # 获取叙事台词
    'format_tech_with_living',     # 格式化：原术语 → 新命名
    'NARRATIVE_LINES',            # 叙事台词库
]


def boot_narrative() -> str:
    """启动叙事"""
    return NARRATIVE_LINES.get('boot', '生命之树正在苏醒...')


def welcome_narrative() -> str:
    """欢迎叙事"""
    return NARRATIVE_LINES.get('welcome', '欢迎回来，旅人。')


def assembly_start_narrative() -> str:
    """装配开始叙事"""
    return NARRATIVE_LINES.get('assembly_start', '根系装配园开启...')


def assembly_success_narrative() -> str:
    """装配成功叙事"""
    return NARRATIVE_LINES.get('assembly_success', '新苗扎根成功...')


def network_connected_narrative(count: int) -> str:
    """网络连接叙事"""
    return get_narrative('network_connected', count=count)


def error_narrative(error_type: str = 'generic') -> str:
    """错误叙事"""
    key = f'error_{error_type}'
    return NARRATIVE_LINES.get(key, NARRATIVE_LINES.get('error_generic'))
