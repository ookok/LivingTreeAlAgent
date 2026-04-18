"""
🌱 根系装配园 (Root Assembly Garden)
====================================

核心理念：让开源库像外来种一样在苗圃中培育，然后嫁接到生命之树

七阶嫁接管线（工具装配）：
1. 良种搜寻台 (Seed Scouting Table) - 输入解析
2. 良种雷达 (Seed Radar) - 库发现
3. 亲和试验台 (Affinity Test Bench) - 冲突检测
4. 园丁指挥台 (Gardener Command) - 用户决策
5. 育苗温床 (Sapling Bed) - 沙箱安装
6. 萌芽试炼场 (Sprout Trial Ground) - 测试验证
7. 扎根部署 (Rooting Deploy) - 动态上线

知识孵化管线（知识生成）：
1. 🌾 沃土播种 (Soil Sowing) - 知识库生成
2. 🛠️ 技能嫁接 (Skill Grafting) - Skill生成
3. 🔄 园丁整理架 (Gardener's Shelf) - 自动整理

🌲 知识林地管线（知识呈现）：
1. 🏛️ 行业林区 (Industry Grove) - 按行业组织知识
2. 📖 Wiki渲染 (Wiki Rendering) - 伪域名路由+静态HTML
3. 📦 LTKG包 (LTKG Package) - 导入导出分享
"""

from .navigator import StarNavigator
from .radar import OSSRadar
from .conflict import ConflictDetector
from .isolation_bay import IsolationBay
from .adapter_gen import AdapterGenerator
from .proving_grounds import ProvingGrounds
from .deployment_bay import DeploymentBay
from .assembler_core import RootAssemblyGarden, AssemblySession, AssemblyStage

# 知识孵化模块
from .knowledge_incubator import KnowledgeBank, KnowledgeEntry, KnowledgeType, GeneratedSkill
from .soil_sowing import SoilSower, MarkdownParser, URLParser, CodebaseParser
from .skill_grafting import SkillGrafting, CodeAnalyzer, CodeAnalysis, CodeFunction
from .gardeners_shelf import GardenersShelf, Deduplicator, AutoTagger, IndexManager

# 🌲 知识林地模块
from .knowledge_grove import (
    KnowledgeGrove, GroveKnowledgeEntry, IndustryIndex,
    Industry, INDUSTRY_NAMES, get_grove
)
from .wiki_renderer import WikiRenderer, get_wiki_renderer
from .ltkg_handler import (
    LTKGHandler, LTKGManifest, ImportStrategy,
    ImportResult, ExportResult, get_ltkg_handler
)

# 📝 智能填表增强模块
from ..page_os.form_filler import (
    FormParser,
    FormField,
    FieldType,
    FieldSemanticType,
    FieldSource,
    AutoFillEngine,
    FillSuggestion,
    FillSource,
    FillPriority,
    FieldEnhancementUI,
    SuggestionCard,
    FieldState,
    FormMemory,
    FieldValueRecord,
    FieldPattern,
    FormatNormalizer,
    FormatRule,
    FormatType,
)

__all__ = [
    # 核心组件
    'RootAssemblyGarden',
    'StarNavigator',
    'OSSRadar',
    'ConflictDetector',
    'IsolationBay',
    'AdapterGenerator',
    'ProvingGrounds',
    'DeploymentBay',
    'AssemblySession',
    'AssemblyStage',

    # 知识孵化
    'KnowledgeBank',
    'KnowledgeEntry',
    'KnowledgeType',
    'GeneratedSkill',

    # 播种器
    'SoilSower',
    'MarkdownParser',
    'URLParser',
    'CodebaseParser',

    # 嫁接器
    'SkillGrafting',
    'CodeAnalyzer',
    'CodeAnalysis',
    'CodeFunction',

    # 整理架
    'GardenersShelf',
    'Deduplicator',
    'AutoTagger',
    'IndexManager',

    # 🌲 知识林地
    'KnowledgeGrove',
    'GroveKnowledgeEntry',
    'IndustryIndex',
    'Industry',
    'INDUSTRY_NAMES',
    'WikiRenderer',
    'LTKGHandler',
    'LTKGManifest',
    'ImportStrategy',
    'ImportResult',
    'ExportResult',

    # 📝 智能填表增强
    'FormParser',
    'FormField',
    'FieldType',
    'FieldSemanticType',
    'FieldSource',
    'AutoFillEngine',
    'FillSuggestion',
    'FillSource',
    'FillPriority',
    'FieldEnhancementUI',
    'SuggestionCard',
    'FieldState',
    'FormMemory',
    'FieldValueRecord',
    'FieldPattern',
    'FormatNormalizer',
    'FormatRule',
    'FormatType',
]


def get_assembler() -> RootAssemblyGarden:
    """获取根系装配园单例"""
    return RootAssemblyGarden.get_instance()


def get_knowledge_bank(base_path: str = None) -> KnowledgeBank:
    """获取知识库管理器"""
    return KnowledgeBank(base_path)


def get_incubator(knowledge_bank: KnowledgeBank = None, llm_client=None):
    """
    获取知识孵化器

    Returns:
        (soil_sower, skill_grafting, gardeners_shelf)
    """
    if knowledge_bank is None:
        knowledge_bank = get_knowledge_bank()

    soil_sower = SoilSower(knowledge_bank, llm_client)
    skill_grafting = SkillGrafting(knowledge_bank)
    gardeners_shelf = GardenersShelf(knowledge_bank)

    return soil_sower, skill_grafting, gardeners_shelf


def get_knowledge_grove(base_path: str = None) -> KnowledgeGrove:
    """获取知识林地管理器"""
    return KnowledgeGrove(base_path)


def get_wiki_renderer(grove: KnowledgeGrove = None) -> WikiRenderer:
    """获取Wiki渲染器"""
    if grove is None:
        grove = get_knowledge_grove()
    return WikiRenderer(grove)


def get_ltkg_handler(grove: KnowledgeGrove = None) -> LTKGHandler:
    """获取LTKG处理器"""
    if grove is None:
        grove = get_knowledge_grove()
    return LTKGHandler(grove)


def get_form_parser() -> FormParser:
    """获取表单解析器"""
    return FormParser()


def get_auto_fill_engine(knowledge_base=None, llm_client=None) -> AutoFillEngine:
    """获取智能填表引擎"""
    return AutoFillEngine(knowledge_base, llm_client)


def get_form_memory(storage_path: str = None) -> FormMemory:
    """获取跨页字段记忆"""
    return FormMemory(storage_path)


def get_format_normalizer() -> FormatNormalizer:
    """获取格式校正器"""
    return FormatNormalizer()
