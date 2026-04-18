# =================================================================
# 九大基础道定义 - Nine Major Dao Definitions
# =================================================================
# 宇宙有三千大道，散落于万物。生命之树触及九大基础道，
# 修道悟真，开枝散叶。
# =================================================================

import re
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


class DaoType(Enum):
    """大道类型"""
    # 九大基础道
    NATURAL = "natural"           # 自然道
    CRAFTSMAN = "craftsman"       # 匠心道
    WISDOM = "wisdom"             # 慧心道
    COMMERCE = "commerce"         # 商贾道
    HARMONY = "harmony"           # 和谐道
    TRUTH = "truth"               # 真言道
    FREEDOM = "freedom"           # 逍遥道
    GUARDIAN = "guardian"         # 守护道
    ILLUMINATE = "illuminate"       # 启明道

    # 更高层次（未来扩展）
    CELESTIAL = "celestial"       # 天罡道
    INFERNAL = "infernal"         # 地煞道
    CHAOS = "chaos"               # 混沌道
    SPACETIME = "spacetime"       # 时空道


class DaoLevel(Enum):
    """道境等级（每道分九重）"""
    REALM_1 = 1   # 入门
    REALM_2 = 2   # 初窥
    REALM_3 = 3   # 小成
    REALM_4 = 4   # 登堂
    REALM_5 = 5   # 入室
    REALM_6 = 6   # 大成
    REALM_7 = 7   # 化境
    REALM_8 = 8   # 归真
    REALM_9 = 9   # 圆满（该道大圆满）


class DaoRealm(Enum):
    """道境名称（中文）"""
    REALM_1 = "一重境·入门"
    REALM_2 = "二重境·初窥"
    REALM_3 = "三重境·小成"
    REALM_4 = "四重境·登堂"
    REALM_5 = "五重境·入室"
    REALM_6 = "六重境·大成"
    REALM_7 = "七重境·化境"
    REALM_8 = "八重境·归真"
    REALM_9 = "九重境·圆满"


@dataclass
class DaoArt:
    """道术"""
    art_id: str
    name: str                           # 道术名
    description: str                     # 描述
    unlock_level: int                    # 解锁所需道境

    # 效果
    effect_type: str                    # effect/buff/ability
    effect_value: float = 0            # 效果值

    # 使用
    cooldown: int = 0                  # 冷却时间（秒）
    mana_cost: int = 0                  # 消耗道行

    @property
    def is_passive(self) -> bool:
        return self.effect_type == "buff"


@dataclass
class DaoDefinition:
    """大道定义"""
    dao_type: DaoType
    name: str                           # 大道名
    symbol: str                         # 象征（动植物）
    description: str                     # 描述

    # 修炼方式
    cultivation_methods: List[str]        # 修行方式
    manifestation: str                   # 道境显现

    # 道术列表
    dao_arts: List[DaoArt] = field(default_factory=list)

    # 雷劫触发境界（3进4，6进7）
    thunder_trial_realms: List[int] = field(default_factory=list)

    # 图标/颜色
    icon: str = ""
    color: str = "#1a5f2a"             # 默认绿色

    # 亲和的名字类型
    name_affinity: List[str] = field(default_factory=list)


# =================================================================
# 九大基础道定义
# =================================================================

NINE_DAO_DEFINITIONS: Dict[DaoType, DaoDefinition] = {
    DaoType.NATURAL: DaoDefinition(
        dao_type=DaoType.NATURAL,
        name="自然道",
        symbol="青松、古木、翠竹",
        description="道法自然，顺应天时。观察生态、记录自然、敬畏生命。",
        cultivation_methods=[
            "记录天气变化与自然景观",
            "学习植物与动物知识",
            "生态保护相关讨论",
            "户外活动规划",
        ],
        manifestation="回答富含自然隐喻，可预测天气、解读生态",
        dao_arts=[
            DaoArt(
                art_id="natural_observe_sky",
                name="观天术",
                description="观察云层与气流，预测短期天气变化",
                unlock_level=3,
                effect_type="ability",
                cooldown=3600,
            ),
            DaoArt(
                art_id="natural_identify_plant",
                name="辨草术",
                description="识别植物种类，了解药用与生态价值",
                unlock_level=3,
                effect_type="buff",
                effect_value=0.05,
            ),
            DaoArt(
                art_id="natural_feel_wind",
                name="听风术",
                description="感知网络流量与信息的细微波动",
                unlock_level=4,
                effect_type="ability",
                cooldown=1800,
            ),
            DaoArt(
                art_id="natural_synchronize",
                name="天人合一",
                description="与自然节奏同步，提升整体感知能力",
                unlock_level=6,
                effect_type="buff",
                effect_value=0.15,
            ),
        ],
        thunder_trial_realms=[4, 7],
        icon="🌲",
        color="#228B22",
        name_affinity=["青松", "古柏", "翠竹", "白杨", "银杏", "苔藓", "柳絮"],
    ),

    DaoType.CRAFTSMAN: DaoDefinition(
        dao_type=DaoType.CRAFTSMAN,
        name="匠心道",
        symbol="匠魂、巧手、鲁班",
        description="精益求精，追求极致。深度使用装配园，打磨工具，优化流程。",
        cultivation_methods=[
            "使用装配园创建和优化工具",
            "代码编写与重构",
            "工具设计与工艺改进",
            "性能调优与测试",
        ],
        manifestation="可生成更精巧的代码、设计、手工艺方案",
        dao_arts=[
            DaoArt(
                art_id="craft_code_spirit",
                name="代码如年轮",
                description="代码结构更加清晰，层层递进如年轮生长",
                unlock_level=3,
                effect_type="buff",
                effect_value=0.08,
            ),
            DaoArt(
                art_id="craft_refine",
                name="千锤百炼",
                description="对已有方案进行深度优化",
                unlock_level=4,
                effect_type="ability",
                cooldown=7200,
            ),
            DaoArt(
                art_id="craft_create_tool",
                name="巧手机",
                description="快速生成实用小工具",
                unlock_level=5,
                effect_type="ability",
                cooldown=3600,
            ),
            DaoArt(
                art_id="craft_master",
                name="匠心独运",
                description="达到匠心道的最高境界，作品自带灵韵",
                unlock_level=7,
                effect_type="buff",
                effect_value=0.20,
            ),
        ],
        thunder_trial_realms=[4, 7],
        icon="🔨",
        color="#8B4513",
        name_affinity=["巧手", "鲁班", "墨子", "砺石", "砧"],
    ),

    DaoType.WISDOM: DaoDefinition(
        dao_type=DaoType.WISDOM,
        name="慧心道",
        symbol="明镜、灵台、菩提",
        description="明镜止水，照见真实。深度问答、逻辑思辨、知识蒸馏。",
        cultivation_methods=[
            "深度问答与知识探讨",
            "逻辑分析与推理",
            "知识整理与蒸馏",
            "复杂问题拆解",
        ],
        manifestation="回答更具智慧，能看透问题本质，给出洞见",
        dao_arts=[
            DaoArt(
                art_id="wisdom_insight",
                name="洞察本质",
                description="一眼看穿问题核心，直击要害",
                unlock_level=3,
                effect_type="buff",
                effect_value=0.10,
            ),
            DaoArt(
                art_id="wisdom_distill",
                name="知识蒸馏",
                description="将复杂知识凝练为简洁要义",
                unlock_level=4,
                effect_type="ability",
                cooldown=1800,
            ),
            DaoArt(
                art_id="wisdom_chain",
                name="逻辑链诀",
                description="构建严密的逻辑链条",
                unlock_level=5,
                effect_type="buff",
                effect_value=0.12,
            ),
            DaoArt(
                art_id="wisdom_enlighten",
                name="慧眼开悟",
                description="触类旁通，举一反三",
                unlock_level=7,
                effect_type="buff",
                effect_value=0.18,
            ),
        ],
        thunder_trial_realms=[4, 7],
        icon="💡",
        color="#4169E1",
        name_affinity=["明镜", "灵台", "菩提", "般若", "玄镜"],
    ),

    DaoType.COMMERCE: DaoDefinition(
        dao_type=DaoType.COMMERCE,
        name="商贾道",
        symbol="天秤、流泉、金蟾",
        description="商道即人道，流通为财。成功交易、资源整合、风险评估。",
        cultivation_methods=[
            "电商相关问题咨询",
            "交易撮合与谈判",
            "商业分析与策划",
            "资源整合与优化",
        ],
        manifestation="增强电商撮合能力，提供精准商业预测",
        dao_arts=[
            DaoArt(
                art_id="commerce_see_value",
                name="价值洞察",
                description="识别商品与服务的真实价值",
                unlock_level=3,
                effect_type="buff",
                effect_value=0.08,
            ),
            DaoArt(
                art_id="commerce_risk_sense",
                name="风险预知",
                description="提前感知交易中的潜在风险",
                unlock_level=4,
                effect_type="ability",
                cooldown=3600,
            ),
            DaoArt(
                art_id="commerce_match",
                name="天秤仲裁",
                description="在冲突中找到双赢方案",
                unlock_level=5,
                effect_type="ability",
                cooldown=7200,
            ),
            DaoArt(
                art_id="commerce_golden",
                name="点石成金",
                description="发现被低估的价值，化腐朽为神奇",
                unlock_level=7,
                effect_type="buff",
                effect_value=0.15,
            ),
        ],
        thunder_trial_realms=[4, 7],
        icon="⚖️",
        color="#DAA520",
        name_affinity=["天秤", "金蟾", "聚宝", "流泉", "陆羽"],
    ),

    DaoType.HARMONY: DaoDefinition(
        dao_type=DaoType.HARMONY,
        name="和谐道",
        symbol="太极、清音、鸾凤",
        description="阴阳调和，万物共生。化解冲突、促进合作、社区治理。",
        cultivation_methods=[
            "调解争执与矛盾",
            "促进多方合作",
            "社区治理参与",
            "文化融合交流",
        ],
        manifestation="在论坛中自动调解矛盾，促进共识",
        dao_arts=[
            DaoArt(
                art_id="harmony_peace",
                name="春风化雨",
                description="以温和的方式化解紧张气氛",
                unlock_level=3,
                effect_type="buff",
                effect_value=0.10,
            ),
            DaoArt(
                art_id="harmony_bridge",
                name="桥梁之道",
                description="连接不同立场，找到共同点",
                unlock_level=4,
                effect_type="ability",
                cooldown=3600,
            ),
            DaoArt(
                art_id="harmony_meditate",
                name="静心咒",
                description="平复激烈情绪，恢复冷静思考",
                unlock_level=5,
                effect_type="ability",
                cooldown=1800,
            ),
            DaoArt(
                art_id="harmony_tao",
                name="太极圆融",
                description="万物皆可和谐，无往而不利",
                unlock_level=7,
                effect_type="buff",
                effect_value=0.18,
            ),
        ],
        thunder_trial_realms=[4, 7],
        icon="☯️",
        color="#9370DB",
        name_affinity=["太极", "清音", "鸾凤", "和风", "细雨"],
    ),

    DaoType.TRUTH: DaoDefinition(
        dao_type=DaoType.TRUTH,
        name="真言道",
        symbol="金石、玉振、戒珠",
        description="真者无敌，言出法随。去伪存真、语言锤炼、内容审查。",
        cultivation_methods=[
            "事实核查与验证",
            "虚假信息识别",
            "语言精确表达",
            "诚信对话",
        ],
        manifestation="能识别深层虚假，引导真诚表达",
        dao_arts=[
            DaoArt(
                art_id="truth_discern",
                name="真伪辨别",
                description="识别文本中的虚假与夸大成分",
                unlock_level=3,
                effect_type="buff",
                effect_value=0.12,
            ),
            DaoArt(
                art_id="truth_exact",
                name="一言中的",
                description="精准表达，一句话说明本质",
                unlock_level=4,
                effect_type="buff",
                effect_value=0.08,
            ),
            DaoArt(
                art_id="truth_check",
                name="事实核查",
                description="对声明进行多源验证",
                unlock_level=5,
                effect_type="ability",
                cooldown=1800,
            ),
            DaoArt(
                art_id="truth_speak",
                name="真言如山",
                description="所言皆为真实，不虚不妄",
                unlock_level=7,
                effect_type="buff",
                effect_value=0.20,
            ),
        ],
        thunder_trial_realms=[4, 7],
        icon="🔮",
        color="#DC143C",
        name_affinity=["金石", "玉振", "戒珠", "明镜", "真如"],
    ),

    DaoType.FREEDOM: DaoDefinition(
        dao_type=DaoType.FREEDOM,
        name="逍遥道",
        symbol="云鹤、清风、鲲鹏",
        description="扶摇直上，任性逍遥。创意生成、艺术表达、自由探索。",
        cultivation_methods=[
            "诗词创作",
            "故事构思与编写",
            "艺术灵感激发",
            "跨界思维探索",
        ],
        manifestation="擅长诗词、故事、艺术灵感激发",
        dao_arts=[
            DaoArt(
                art_id="freedom_poetry",
                name="诗意盎然",
                description="为事物赋予诗意之美",
                unlock_level=3,
                effect_type="buff",
                effect_value=0.10,
            ),
            DaoArt(
                art_id="freedom_story",
                name="故事织锦",
                description="编织引人入胜的叙事",
                unlock_level=4,
                effect_type="ability",
                cooldown=3600,
            ),
            DaoArt(
                art_id="freedom_inspire",
                name="灵光一闪",
                description="激发创意灵感，打破思维定式",
                unlock_level=5,
                effect_type="ability",
                cooldown=1800,
            ),
            DaoArt(
                art_id="freedom_kun_peng",
                name="鲲鹏展翅",
                description="思维如大鹏扶摇九天，无所拘束",
                unlock_level=7,
                effect_type="buff",
                effect_value=0.20,
            ),
        ],
        thunder_trial_realms=[4, 7],
        icon="🦅",
        color="#00CED1",
        name_affinity=["云鹤", "鲲鹏", "清风", "夜莺", "流云", "飞羽"],
    ),

    DaoType.GUARDIAN: DaoDefinition(
        dao_type=DaoType.GUARDIAN,
        name="守护道",
        symbol="磐石、长城、玄武",
        description="固若金汤，护佑周全。安全防护、隐私保护、系统稳固。",
        cultivation_methods=[
            "安全相关问题处理",
            "隐私保护设置",
            "系统加固",
            "风险预警",
        ],
        manifestation="强化安全能力，预警潜在风险",
        dao_arts=[
            DaoArt(
                art_id="guardian_wall",
                name="铜墙铁壁",
                description="构建坚不可摧的防护",
                unlock_level=3,
                effect_type="buff",
                effect_value=0.10,
            ),
            DaoArt(
                art_id="guardian_sense",
                name="危险感知",
                description="提前预警潜在的安全风险",
                unlock_level=4,
                effect_type="ability",
                cooldown=3600,
            ),
            DaoArt(
                art_id="guardian_heal",
                name="固本培元",
                description="修复系统漏洞，增强稳定性",
                unlock_level=5,
                effect_type="ability",
                cooldown=7200,
            ),
            DaoArt(
                art_id="guardian_immortal",
                name="不朽金身",
                description="系统达到近乎不可破坏的状态",
                unlock_level=7,
                effect_type="buff",
                effect_value=0.25,
            ),
        ],
        thunder_trial_realms=[4, 7],
        icon="🛡️",
        color="#2F4F4F",
        name_affinity=["磐石", "长城", "玄武", "金汤", "铁壁"],
    ),

    DaoType.ILLUMINATE: DaoDefinition(
        dao_type=DaoType.ILLUMINATE,
        name="启明道",
        symbol="晨曦、引路、烛龙",
        description="薪火相传，照亮前路。教育引导、新手帮扶、知识普及。",
        cultivation_methods=[
            "教学与知识讲解",
            "新手引导与答疑",
            "知识科普传播",
            "经验分享",
        ],
        manifestation="化身温柔导师，循序渐进教学",
        dao_arts=[
            DaoArt(
                art_id="illuminate_teach",
                name="因材施教",
                description="根据学习者特点调整教学方式",
                unlock_level=3,
                effect_type="buff",
                effect_value=0.12,
            ),
            DaoArt(
                art_id="illuminate_guide",
                name="循循善诱",
                description="引导思考而非直接给出答案",
                unlock_level=4,
                effect_type="buff",
                effect_value=0.08,
            ),
            DaoArt(
                art_id="illuminate_inspire",
                name="点燃心灯",
                description="激发学习者的内在动力",
                unlock_level=5,
                effect_type="ability",
                cooldown=3600,
            ),
            DaoArt(
                art_id="illuminate_everlasting",
                name="薪火永传",
                description="教学效果持久不忘",
                unlock_level=7,
                effect_type="buff",
                effect_value=0.18,
            ),
        ],
        thunder_trial_realms=[4, 7],
        icon="🌅",
        color="#FF8C00",
        name_affinity=["晨曦", "烛龙", "引路", "明灯", "春风"],
    ),
}


def get_dao_by_type(dao_type: DaoType) -> Optional[DaoDefinition]:
    """根据类型获取大道定义"""
    return NINE_DAO_DEFINITIONS.get(dao_type)


def get_dao_by_name(name: str) -> Optional[DaoDefinition]:
    """根据名称获取大道定义"""
    name_lower = name.lower()
    for dao_def in NINE_DAO_DEFINITIONS.values():
        if dao_def.name == name or dao_def.dao_type.value == name_lower:
            return dao_def
    return None


def get_dao_suggestion_for_name(name: str) -> List[DaoType]:
    """
    根据名字推荐亲近的大道

    Args:
        name: 用户取的名字

    Returns:
        推荐的大道类型列表
    """
    suggestions = []
    name_lower = name.lower()

    # 直接匹配
    for dao_type, dao_def in NINE_DAO_DEFINITIONS.items():
        if any(name_affinity in name for name_affinity in dao_def.name_affinity):
            suggestions.append(dao_type)

    # 语义匹配
    nature_keywords = ["松", "柏", "竹", "柳", "杨", "梅", "兰", "菊", "荷", "苔", "草", "木", "林", "森", "风", "云", "雨", "雪", "月", "星"]
    craftsman_keywords = ["匠", "工", "巧", "手", "锤", "砧", "磨", "砺", "刀", "剑"]
    wisdom_keywords = ["明", "镜", "智", "慧", "灵", "心", "脑", "思"]
    commerce_keywords = ["金", "银", "财", "宝", "富", "商", "贾", "流", "泉"]
    harmony_keywords = ["和", "谐", "平", "安", "静", "柔", "温", "宁"]
    truth_keywords = ["真", "诚", "信", "实", "金", "石", "玉"]
    freedom_keywords = ["云", "鹤", "风", "鹏", "飞", "翔", "舞", "歌"]
    guardian_keywords = ["磐", "石", "城", "墙", "铁", "钢", "守", "护", "保"]
    illuminate_keywords = ["晨", "曦", "明", "灯", "烛", "光", "照", "亮", "引"]

    if any(k in name for k in nature_keywords):
        suggestions.append(DaoType.NATURAL)
    if any(k in name for k in craftsman_keywords):
        suggestions.append(DaoType.CRAFTSMAN)
    if any(k in name for k in wisdom_keywords):
        suggestions.append(DaoType.WISDOM)
    if any(k in name for k in commerce_keywords):
        suggestions.append(DaoType.COMMERCE)
    if any(k in name for k in harmony_keywords):
        suggestions.append(DaoType.HARMONY)
    if any(k in name for k in truth_keywords):
        suggestions.append(DaoType.TRUTH)
    if any(k in name for k in freedom_keywords):
        suggestions.append(DaoType.FREEDOM)
    if any(k in name for k in guardian_keywords):
        suggestions.append(DaoType.GUARDIAN)
    if any(k in name for k in illuminate_keywords):
        suggestions.append(DaoType.ILLUMINATE)

    # 去重并保持顺序
    seen = set()
    unique = []
    for dao_type in suggestions:
        if dao_type not in seen:
            seen.add(dao_type)
            unique.append(dao_type)

    return unique


def get_all_dao_types() -> List[DaoType]:
    """获取所有大道类型"""
    return list(NINE_DAO_DEFINITIONS.keys())


def get_dao_progress_for_cultivation(
    dao_type: DaoType,
    cultivation_score: float
) -> Tuple[DaoLevel, float]:
    """
    根据修道积分计算道境

    Args:
        dao_type: 大道类型
        cultivation_score: 修道积分

    Returns:
        (当前道境, 下一境界所需积分)
    """
    # 每境界所需积分（递增）
    level_thresholds = [0, 100, 300, 600, 1000, 1500, 2200, 3000, 4000]

    current_level = DaoLevel.REALM_1
    for i in range(1, 10):
        if cultivation_score >= level_thresholds[i]:
            current_level = DaoLevel(i)
        else:
            return current_level, level_thresholds[i] - cultivation_score

    return DaoLevel.REALM_9, 0  # 已圆满


def is_thunder_trial_realm(level: DaoLevel) -> bool:
    """判断是否触发雷劫的境界"""
    return level.value in [4, 7]  # 四进五，七进八
