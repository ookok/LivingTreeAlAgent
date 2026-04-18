# =================================================================
# 通用智能填表增强模块 - Form Filler
# =================================================================
# 设计目标：
# - 通用性：适配 80% 的常见 Web 表单
# - 智能性：结合知识库、历史记录、上下文语义
# - 人机协同：增强而非替代，用户保持控制
# - 体验一流：非模态浮层，不打断操作流
#
# 核心模块：
# - form_parser: 表单智能解析器
# - auto_fill_engine: 智能填表引擎
# - field_ui: 字段级悬浮建议卡
# - form_memory: 跨页字段记忆
# - format_normalizer: 格式自动校正
# =================================================================

from .form_parser import (
    FormParser,
    FormField,
    FieldType,
    FieldSemanticType,
    FieldSource,
)
from .auto_fill_engine import (
    AutoFillEngine,
    FillSuggestion,
    FillSource,
    FillPriority,
)
from .field_ui import (
    FieldEnhancementUI,
    SuggestionCard,
    FieldState,
)
from .form_memory import (
    FormMemory,
    FieldValueRecord,
    FieldPattern,
)
from .format_normalizer import (
    FormatNormalizer,
    FormatRule,
    FormatType,
)

__all__ = [
    # Form Parser
    'FormParser',
    'FormField',
    'FieldType',
    'FieldSemanticType',
    'FieldSource',

    # Auto Fill Engine
    'AutoFillEngine',
    'FillSuggestion',
    'FillSource',
    'FillPriority',

    # Field UI
    'FieldEnhancementUI',
    'SuggestionCard',
    'FieldState',

    # Form Memory
    'FormMemory',
    'FieldValueRecord',
    'FieldPattern',

    # Format Normalizer
    'FormatNormalizer',
    'FormatRule',
    'FormatType',
]
