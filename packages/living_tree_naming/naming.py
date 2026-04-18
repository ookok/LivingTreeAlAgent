"""
Living Tree Naming - 生命之树命名对照表

技术概念 → 生命之树命名
"""

from typing import Dict, Optional
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# 顶层架构
# ═══════════════════════════════════════════════════════════════════════════════

TOP_LEVEL = {
    "client": "生命主干 (The Trunk)",
    "root_network": "根系网络 (The Root Network)",
    "ai_core": "智慧树芯 (The Heartwood)",
    "data_base": "沃土库 (The Soil Bank)",
}

# ═══════════════════════════════════════════════════════════════════════════════
# 智能与进化
# ═══════════════════════════════════════════════════════════════════════════════

AI_INTELLIGENCE = {
    "hermes_agent": "信使叶灵 (Leaf Messenger)",
    "self_patch": "愈伤机制 (Cambium Repair)",
    "patch_distribution": "花粉传播 (Pollen Drift)",
    "knowledge_distillation": "蜜露酿制 (Nectar Refining)",
    "intent_recognition": "光合感应 (Photosensory)",
}

# ═══════════════════════════════════════════════════════════════════════════════
# 网络与通信
# ═══════════════════════════════════════════════════════════════════════════════

NETWORK = {
    "node_discovery": "根须触碰 (Root Contact)",
    "pseudo_domain": "林间记号 (Forest Sigil)",
    "broadcast": "季风广播 (Monsoon Cast)",
    "relay_service": "水源泉眼 (The Springhead)",
}

# ═══════════════════════════════════════════════════════════════════════════════
# 邮箱与消息
# ═══════════════════════════════════════════════════════════════════════════════

MAIL = {
    "external_mail": "飞鸟邮驿 (Songbird Post)",
    "internal_mail": "脉动信囊 (Sap Channel)",
    "mail_sync": "雨露渗透 (Rain Seep)",
}

# ═══════════════════════════════════════════════════════════════════════════════
# 工具与装配
# ═══════════════════════════════════════════════════════════════════════════════

ASSEMBLY = {
    "assembler": "根系装配园 (Root Assembly Garden)",
    "library_scan": "良种搜寻 (Seed Scouting)",
    "conflict_detection": "亲和试验 (Affinity Test)",
    "sandbox": "育苗温床 (Sapling Bed)",
    "test_ui": "萌芽试炼 (Sprout Trial)",
}

# ═══════════════════════════════════════════════════════════════════════════════
# UI与交互
# ═══════════════════════════════════════════════════════════════════════════════

UI = {
    "main_window": "林窗视图 (Canopy Vista)",
    "chat_window": "年轮对话 (Ring Dialogue)",
    "settings": "根系调节 (Root Tuner)",
    "toast": "晨露提示 (Dewdrop Hint)",
}

# ═══════════════════════════════════════════════════════════════════════════════
# 合并对照表
# ═══════════════════════════════════════════════════════════════════════════════

NAMING_TABLE = {
    **TOP_LEVEL,
    **AI_INTELLIGENCE,
    **NETWORK,
    **MAIL,
    **ASSEMBLY,
    **UI,
}


def get_living_name(technical_term: str) -> str:
    """
    获取技术术语的生命之树命名

    Args:
        technical_term: 技术术语 (如 "assembler", "main_window")

    Returns:
        生命之树命名 (如 "根系装配园 (Root Assembly Garden)")
    """
    return NAMING_TABLE.get(technical_term, technical_term)


def get_technical_name(living_name: str) -> Optional[str]:
    """
    从生命之树命名获取技术术语 (反向查询)

    Args:
        living_name: 生命之树命名

    Returns:
        技术术语，如果未找到则返回None
    """
    for tech, living in NAMING_TABLE.items():
        if living == living_name:
            return tech
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 叙事台词
# ═══════════════════════════════════════════════════════════════════════════════


class NarrativeLines:
    """🌳 生命之树叙事台词"""

    # 启动
    BOOT_LINES = [
        "生命之树正在苏醒...",
        "根系开始向远方延伸...",
        "林间的光芒正在唤醒",
    ]

    # 欢迎
    WELCOME_LINES = [
        "欢迎回来，旅人。林间交易的风已经开始流动，发现 {count} 个潜在信号。",
        "您好，森林旅人。当前根系状态良好，{nodes} 个共生伙伴在线。",
        "检测到新活动，{count} 条消息等待。信使叶灵随时待命。",
    ]

    # 交易
    TRADE_LINES = [
        "新的果实成熟了，等待交换...",
        "风媒牵线成功，发现潜在的交易伙伴...",
        "落叶归根，交易达成，年轮烙印已更新",
    ]

    # 嫁接/装配
    GRAFT_LINES = [
        "根系装配园开启，开始搜寻良种...",
        "嫁接过程开始，新苗正在扎根...",
        "嫁接成功，新能力已在林间绽放",
    ]

    # 警告
    WARNING_LINES = [
        "林间起了风浪，请注意...",
        "根系信号波动，连接可能不稳定",
        "有新消息如晨露般降临",
    ]

    # 成功
    SUCCESS_LINES = [
        "能量在枝干中流动，一切就绪",
        "新的共生连接已建立",
        "雨露渗透成功，知识已融入沃土",
    ]

    @classmethod
    def get_welcome_line(cls, count: int = 0, nodes: int = 0) -> str:
        """获取欢迎台词"""
        import random
        line = random.choice(cls.WELCOME_LINES)
        return line.format(count=count, nodes=nodes)

    @classmethod
    def get_trade_line(cls) -> str:
        """获取交易台词"""
        import random
        return random.choice(cls.TRADE_LINES)

    @classmethod
    def get_boot_line(cls) -> str:
        """获取启动台词"""
        import random
        return random.choice(cls.BOOT_LINES)

    @classmethod
    def get_graft_line(cls) -> str:
        """获取嫁接台词"""
        import random
        return random.choice(cls.GRAFT_LINES)


def get_narrative(scene: str, **kwargs) -> str:
    """
    获取叙事台词

    Args:
        scene: 场景 (boot, welcome, trade, graft, warning, success)
        **kwargs: 格式化参数

    Returns:
        叙事台词
    """
    lines = {
        "boot": NarrativeLines.BOOT_LINES,
        "welcome": NarrativeLines.WELCOME_LINES,
        "trade": NarrativeLines.TRADE_LINES,
        "graft": NarrativeLines.GRAFT_LINES,
        "warning": NarrativeLines.WARNING_LINES,
        "success": NarrativeLines.SUCCESS_LINES,
    }

    import random
    line_list = lines.get(scene, lines["boot"])
    line = random.choice(line_list)

    if kwargs:
        try:
            line = line.format(**kwargs)
        except KeyError:
            pass

    return line
