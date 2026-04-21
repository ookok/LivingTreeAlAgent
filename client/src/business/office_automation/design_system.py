"""
🎨 Token 化设计系统

企业级设计系统的 Token 化管理：
- 颜色 Token (品牌色/功能色/语义色)
- 字体 Token (标题/正文/代码/注释)
- 间距 Token (页面/段落/元素)
- 文档主题 (预设主题 + 自定义)

参考 minimax-pdf 的设计理念，支持：
- 情景感知: 根据文档类型自动调整
- 品牌合规: 自动检查品牌规范符合度
- 设计变体: 同一文档类型的多种风格
"""

import json
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path

logger = logging.getLogger(__name__)


# ===== Token 类型定义 =====

class TokenType(Enum):
    """Token 类型"""
    COLOR = "color"
    FONT = "font"
    SPACING = "spacing"
    BORDER = "border"
    SHADOW = "shadow"
    OPACITY = "opacity"


class ColorRole(Enum):
    """颜色语义角色"""
    PRIMARY = "primary"            # 主色
    SECONDARY = "secondary"        # 辅助色
    ACCENT = "accent"              # 强调色
    BACKGROUND = "background"      # 背景色
    SURFACE = "surface"            # 表面色
    TEXT_PRIMARY = "text_primary"  # 主文本色
    TEXT_SECONDARY = "text_secondary"  # 次文本色
    SUCCESS = "success"            # 成功色
    WARNING = "warning"            # 警告色
    ERROR = "error"                # 错误色
    INFO = "info"                  # 信息色
    DIVIDER = "divider"            # 分割线色
    HEADER_BG = "header_bg"        # 页眉背景
    FOOTER_BG = "footer_bg"        # 页脚背景
    COVER_BG = "cover_bg"          # 封面背景


class FontRole(Enum):
    """字体语义角色"""
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    BODY = "body"
    BODY_BOLD = "body_bold"
    CAPTION = "caption"
    CODE = "code"
    FOOTNOTE = "footnote"
    HEADER = "header"
    FOOTER = "footer"


class SpacingRole(Enum):
    """间距语义角色"""
    PAGE_MARGIN = "page_margin"
    SECTION_GAP = "section_gap"
    PARAGRAPH_GAP = "paragraph_gap"
    LINE_HEIGHT = "line_height"
    ELEMENT_GAP = "element_gap"
    TABLE_PADDING = "table_padding"
    LIST_INDENT = "list_indent"
    COVER_PADDING = "cover_padding"


# ===== Token 数据类 =====

@dataclass
class DesignToken:
    """设计 Token 基类"""
    name: str
    token_type: TokenType
    value: Any
    description: str = ""
    category: str = ""
    tags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.token_type.value,
            "value": self.value,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
        }


@dataclass
class ColorToken(DesignToken):
    """颜色 Token"""
    token_type: TokenType = field(default=TokenType.COLOR, init=False)
    hex_value: str = ""
    rgb: tuple = (0, 0, 0)
    opacity: float = 1.0
    role: Optional[ColorRole] = None

    def __post_init__(self):
        if self.hex_value and not self.value:
            self.value = self.hex_value
        if self.hex_value:
            h = self.hex_value.lstrip('#')
            self.rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def with_opacity(self, opacity: float) -> str:
        """返回带透明度的颜色值"""
        r, g, b = self.rgb
        return f"rgba({r}, {g}, {b}, {opacity})"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "hex": self.hex_value,
            "rgb": self.rgb,
            "opacity": self.opacity,
            "role": self.role.value if self.role else None,
        })
        return d


@dataclass
class FontToken(DesignToken):
    """字体 Token"""
    token_type: TokenType = field(default=TokenType.FONT, init=False)
    family: str = "Microsoft YaHei"
    size: int = 12              # pt
    weight: str = "normal"      # normal/bold
    style: str = "normal"       # normal/italic
    line_spacing: float = 1.5   # 倍行距
    role: Optional[FontRole] = None

    def __post_init__(self):
        if not self.value:
            self.value = f"{self.family} {self.size}pt {self.weight}"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "family": self.family,
            "size": self.size,
            "weight": self.weight,
            "style": self.style,
            "line_spacing": self.line_spacing,
            "role": self.role.value if self.role else None,
        })
        return d


@dataclass
class SpacingToken(DesignToken):
    """间距 Token"""
    token_type: TokenType = field(default=TokenType.SPACING, init=False)
    value_pt: float = 0.0       # 磅值
    value_cm: float = 0.0       # 厘米值
    value_inch: float = 0.0     # 英寸值
    role: Optional[SpacingRole] = None

    def __post_init__(self):
        if self.value_pt:
            self.value_cm = self.value_pt / 28.346
            self.value_inch = self.value_pt / 72.0
        elif self.value_cm:
            self.value_pt = self.value_cm * 28.346
            self.value_inch = self.value_cm / 2.54
        elif self.value_inch:
            self.value_pt = self.value_inch * 72.0
            self.value_cm = self.value_inch * 2.54
        if not self.value:
            self.value = f"{self.value_pt:.1f}pt"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "pt": round(self.value_pt, 2),
            "cm": round(self.value_cm, 2),
            "inch": round(self.value_inch, 2),
            "role": self.role.value if self.role else None,
        })
        return d


# ===== 文档主题 =====

class DocumentTheme:
    """
    文档主题 - 包含完整的设计 Token 集合

    预设主题：
    - corporate: 企业正式 (蓝灰色系)
    - creative: 创意设计 (彩色系)
    - minimal: 极简风格 (黑白灰)
    - tech: 科技感 (深蓝色系)
    - warm: 温暖亲切 (暖色系)
    - government: 政务红头 (红金色系)
    """

    # 预设主题定义
    PRESETS = {
        "corporate": {
            "name": "企业正式",
            "colors": {
                ColorRole.PRIMARY: "#1B3A5C",
                ColorRole.SECONDARY: "#4A7FB5",
                ColorRole.ACCENT: "#E8A838",
                ColorRole.BACKGROUND: "#FFFFFF",
                ColorRole.SURFACE: "#F5F7FA",
                ColorRole.TEXT_PRIMARY: "#1A1A2E",
                ColorRole.TEXT_SECONDARY: "#6B7280",
                ColorRole.SUCCESS: "#10B981",
                ColorRole.WARNING: "#F59E0B",
                ColorRole.ERROR: "#EF4444",
                ColorRole.INFO: "#3B82F6",
                ColorRole.HEADER_BG: "#1B3A5C",
                ColorRole.FOOTER_BG: "#F5F7FA",
                ColorRole.COVER_BG: "#1B3A5C",
            },
            "fonts": {
                FontRole.HEADING_1: ("Microsoft YaHei", 22, "bold"),
                FontRole.HEADING_2: ("Microsoft YaHei", 16, "bold"),
                FontRole.HEADING_3: ("Microsoft YaHei", 14, "bold"),
                FontRole.BODY: ("SimSun", 12, "normal"),
                FontRole.CAPTION: ("SimSun", 10, "normal"),
                FontRole.CODE: ("Consolas", 10, "normal"),
            },
            "spacings": {
                SpacingRole.PAGE_MARGIN: 2.54,      # cm
                SpacingRole.SECTION_GAP: 24,          # pt
                SpacingRole.PARAGRAPH_GAP: 12,        # pt
                SpacingRole.LINE_HEIGHT: 1.5,         # multiplier
            },
        },
        "creative": {
            "name": "创意设计",
            "colors": {
                ColorRole.PRIMARY: "#6C5CE7",
                ColorRole.SECONDARY: "#A29BFE",
                ColorRole.ACCENT: "#FD79A8",
                ColorRole.BACKGROUND: "#FFFFFF",
                ColorRole.SURFACE: "#FAFAFE",
                ColorRole.TEXT_PRIMARY: "#2D3436",
                ColorRole.TEXT_SECONDARY: "#636E72",
                ColorRole.SUCCESS: "#00B894",
                ColorRole.WARNING: "#FDCB6E",
                ColorRole.ERROR: "#E17055",
                ColorRole.INFO: "#74B9FF",
                ColorRole.HEADER_BG: "#6C5CE7",
                ColorRole.FOOTER_BG: "#FAFAFE",
                ColorRole.COVER_BG: "#6C5CE7",
            },
            "fonts": {
                FontRole.HEADING_1: ("Microsoft YaHei", 24, "bold"),
                FontRole.HEADING_2: ("Microsoft YaHei", 18, "bold"),
                FontRole.HEADING_3: ("Microsoft YaHei", 14, "bold"),
                FontRole.BODY: ("Microsoft YaHei", 11, "normal"),
                FontRole.CAPTION: ("Microsoft YaHei", 9, "normal"),
                FontRole.CODE: ("Fira Code", 10, "normal"),
            },
            "spacings": {
                SpacingRole.PAGE_MARGIN: 2.0,
                SpacingRole.SECTION_GAP: 28,
                SpacingRole.PARAGRAPH_GAP: 14,
                SpacingRole.LINE_HEIGHT: 1.6,
            },
        },
        "minimal": {
            "name": "极简风格",
            "colors": {
                ColorRole.PRIMARY: "#1A1A1A",
                ColorRole.SECONDARY: "#666666",
                ColorRole.ACCENT: "#1A1A1A",
                ColorRole.BACKGROUND: "#FFFFFF",
                ColorRole.SURFACE: "#FAFAFA",
                ColorRole.TEXT_PRIMARY: "#1A1A1A",
                ColorRole.TEXT_SECONDARY: "#999999",
                ColorRole.SUCCESS: "#2ECC71",
                ColorRole.WARNING: "#F1C40F",
                ColorRole.ERROR: "#E74C3C",
                ColorRole.INFO: "#3498DB",
                ColorRole.HEADER_BG: "#FFFFFF",
                ColorRole.FOOTER_BG: "#FFFFFF",
                ColorRole.COVER_BG: "#1A1A1A",
            },
            "fonts": {
                FontRole.HEADING_1: ("SimHei", 22, "bold"),
                FontRole.HEADING_2: ("SimHei", 16, "bold"),
                FontRole.HEADING_3: ("SimHei", 14, "normal"),
                FontRole.BODY: ("SimSun", 12, "normal"),
                FontRole.CAPTION: ("SimSun", 10, "normal"),
                FontRole.CODE: ("Consolas", 10, "normal"),
            },
            "spacings": {
                SpacingRole.PAGE_MARGIN: 2.54,
                SpacingRole.SECTION_GAP: 20,
                SpacingRole.PARAGRAPH_GAP: 10,
                SpacingRole.LINE_HEIGHT: 1.5,
            },
        },
        "government": {
            "name": "政务红头",
            "colors": {
                ColorRole.PRIMARY: "#CC0000",
                ColorRole.SECONDARY: "#8B0000",
                ColorRole.ACCENT: "#D4A017",
                ColorRole.BACKGROUND: "#FFFFFF",
                ColorRole.SURFACE: "#FFF8F0",
                ColorRole.TEXT_PRIMARY: "#000000",
                ColorRole.TEXT_SECONDARY: "#333333",
                ColorRole.SUCCESS: "#228B22",
                ColorRole.WARNING: "#D4A017",
                ColorRole.ERROR: "#CC0000",
                ColorRole.INFO: "#1B3A5C",
                ColorRole.HEADER_BG: "#CC0000",
                ColorRole.FOOTER_BG: "#FFF8F0",
                ColorRole.COVER_BG: "#CC0000",
            },
            "fonts": {
                FontRole.HEADING_1: ("FangSong", 22, "bold"),
                FontRole.HEADING_2: ("FangSong", 16, "bold"),
                FontRole.HEADING_3: ("FangSong", 14, "bold"),
                FontRole.BODY: ("FangSong", 16, "normal"),    # 公文正文仿宋三号
                FontRole.CAPTION: ("KaiTi", 12, "normal"),
                FontRole.CODE: ("Consolas", 10, "normal"),
            },
            "spacings": {
                SpacingRole.PAGE_MARGIN: 3.7,        # 公文标准上3.7cm
                SpacingRole.SECTION_GAP: 28,
                SpacingRole.PARAGRAPH_GAP: 16,
                SpacingRole.LINE_HEIGHT: 1.6,         # 公文固定值28磅
            },
        },
        "tech": {
            "name": "科技感",
            "colors": {
                ColorRole.PRIMARY: "#0D47A1",
                ColorRole.SECONDARY: "#1565C0",
                ColorRole.ACCENT: "#00E5FF",
                ColorRole.BACKGROUND: "#FFFFFF",
                ColorRole.SURFACE: "#F0F4FF",
                ColorRole.TEXT_PRIMARY: "#212121",
                ColorRole.TEXT_SECONDARY: "#757575",
                ColorRole.SUCCESS: "#00C853",
                ColorRole.WARNING: "#FFAB00",
                ColorRole.ERROR: "#FF1744",
                ColorRole.INFO: "#2979FF",
                ColorRole.HEADER_BG: "#0D47A1",
                ColorRole.FOOTER_BG: "#F0F4FF",
                ColorRole.COVER_BG: "#0D47A1",
            },
            "fonts": {
                FontRole.HEADING_1: ("Microsoft YaHei", 24, "bold"),
                FontRole.HEADING_2: ("Microsoft YaHei", 18, "bold"),
                FontRole.HEADING_3: ("Microsoft YaHei", 14, "bold"),
                FontRole.BODY: ("Microsoft YaHei", 11, "normal"),
                FontRole.CAPTION: ("Microsoft YaHei", 9, "normal"),
                FontRole.CODE: ("JetBrains Mono", 10, "normal"),
            },
            "spacings": {
                SpacingRole.PAGE_MARGIN: 2.0,
                SpacingRole.SECTION_GAP: 24,
                SpacingRole.PARAGRAPH_GAP: 12,
                SpacingRole.LINE_HEIGHT: 1.5,
            },
        },
        "warm": {
            "name": "温暖亲切",
            "colors": {
                ColorRole.PRIMARY: "#D35400",
                ColorRole.SECONDARY: "#E67E22",
                ColorRole.ACCENT: "#E74C3C",
                ColorRole.BACKGROUND: "#FFFBF5",
                ColorRole.SURFACE: "#FFF5EB",
                ColorRole.TEXT_PRIMARY: "#2C3E50",
                ColorRole.TEXT_SECONDARY: "#7F8C8D",
                ColorRole.SUCCESS: "#27AE60",
                ColorRole.WARNING: "#F39C12",
                ColorRole.ERROR: "#C0392B",
                ColorRole.INFO: "#2980B9",
                ColorRole.HEADER_BG: "#D35400",
                ColorRole.FOOTER_BG: "#FFF5EB",
                ColorRole.COVER_BG: "#D35400",
            },
            "fonts": {
                FontRole.HEADING_1: ("Microsoft YaHei", 22, "bold"),
                FontRole.HEADING_2: ("Microsoft YaHei", 16, "bold"),
                FontRole.HEADING_3: ("Microsoft YaHei", 14, "bold"),
                FontRole.BODY: ("KaiTi", 12, "normal"),
                FontRole.CAPTION: ("KaiTi", 10, "normal"),
                FontRole.CODE: ("Consolas", 10, "normal"),
            },
            "spacings": {
                SpacingRole.PAGE_MARGIN: 2.5,
                SpacingRole.SECTION_GAP: 22,
                SpacingRole.PARAGRAPH_GAP: 12,
                SpacingRole.LINE_HEIGHT: 1.6,
            },
        },
    }

    def __init__(self, theme_id: str = "corporate", custom_overrides: dict = None):
        self.theme_id = theme_id
        self.name = ""
        self.colors: Dict[ColorRole, ColorToken] = {}
        self.fonts: Dict[FontRole, FontToken] = {}
        self.spacings: Dict[SpacingRole, SpacingToken] = {}
        self.custom_overrides = custom_overrides or {}

        self._load_preset(theme_id)

        # 应用自定义覆盖
        if custom_overrides:
            self._apply_overrides(custom_overrides)

    def _load_preset(self, theme_id: str):
        """加载预设主题"""
        if theme_id not in self.PRESETS:
            logger.warning(f"未知主题: {theme_id}, 使用 corporate")
            theme_id = "corporate"

        preset = self.PRESETS[theme_id]
        self.theme_id = theme_id
        self.name = preset["name"]

        # 加载颜色 Token
        for role, hex_val in preset.get("colors", {}).items():
            self.colors[role] = ColorToken(
                name=f"color.{role.value}",
                hex_value=hex_val,
                description=f"{self.name} - {role.value}",
                category=self.theme_id,
                role=role,
            )

        # 加载字体 Token
        for role, (family, size, weight) in preset.get("fonts", {}).items():
            self.fonts[role] = FontToken(
                name=f"font.{role.value}",
                family=family,
                size=size,
                weight=weight,
                description=f"{self.name} - {role.value}",
                category=self.theme_id,
                role=role,
            )

        # 加载间距 Token
        for role, value in preset.get("spacings", {}).items():
            if role == SpacingRole.LINE_HEIGHT:
                self.spacings[role] = SpacingToken(
                    name=f"spacing.{role.value}",
                    value=f"{value}x",
                    description=f"{self.name} - {role.value}",
                    category=self.theme_id,
                    role=role,
                )
                self.spacings[role].value_pt = value  # 行距用倍数
            else:
                self.spacings[role] = SpacingToken(
                    name=f"spacing.{role.value}",
                    value_cm=value,
                    description=f"{self.name} - {role.value}",
                    category=self.theme_id,
                    role=role,
                )

    def _apply_overrides(self, overrides: dict):
        """应用自定义覆盖"""
        for key, value in overrides.items():
            if key.startswith("color."):
                role_name = key.split(".", 1)[1]
                try:
                    role = ColorRole(role_name)
                    if role in self.colors:
                        self.colors[role].hex_value = value
                        self.colors[role].__post_init__()
                except ValueError:
                    pass
            elif key.startswith("font."):
                role_name = key.split(".", 1)[1]
                try:
                    role = FontRole(role_name)
                    if role in self.fonts and isinstance(value, tuple):
                        self.fonts[role].family = value[0]
                        self.fonts[role].size = value[1]
                        if len(value) > 2:
                            self.fonts[role].weight = value[2]
                except ValueError:
                    pass

    def get_color(self, role: ColorRole, opacity: float = 1.0) -> str:
        """获取颜色值"""
        token = self.colors.get(role)
        if token:
            if opacity < 1.0:
                return token.with_opacity(opacity)
            return token.hex_value
        return "#000000"

    def get_font(self, role: FontRole) -> FontToken:
        """获取字体 Token"""
        return self.fonts.get(role, FontToken(name="default", family="SimSun", size=12))

    def get_spacing(self, role: SpacingRole) -> SpacingToken:
        """获取间距 Token"""
        return self.spacings.get(role, SpacingToken(name="default", value_cm=2.54))

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "theme_id": self.theme_id,
            "name": self.name,
            "colors": {role.value: t.to_dict() for role, t in self.colors.items()},
            "fonts": {role.value: t.to_dict() for role, t in self.fonts.items()},
            "spacings": {role.value: t.to_dict() for role, t in self.spacings.items()},
        }

    def to_css(self) -> str:
        """导出为 CSS 变量 (用于 HTML/PDF 渲染)"""
        lines = [":root {"]
        for role, token in self.colors.items():
            lines.append(f"  --color-{role.value}: {token.hex_value};")
        for role, token in self.fonts.items():
            lines.append(f"  --font-{role.value}: {token.family};")
            lines.append(f"  --font-{role.value}-size: {token.size}pt;")
        for role, token in self.spacings.items():
            lines.append(f"  --spacing-{role.value}: {token.value};")
        lines.append("}")
        return "\n".join(lines)


# ===== 设计系统管理器 =====

class DesignSystem:
    """
    设计系统管理器

    管理多个主题、提供情景感知的 Token 解析：
    - 根据文档类型推荐主题
    - 根据受众调整颜色/字体
    - 品牌合规检查
    """

    # 文档类型 → 推荐主题映射
    TYPE_THEME_MAP = {
        "report": "corporate",
        "contract": "corporate",
        "proposal": "corporate",
        "resume": "minimal",
        "invoice": "minimal",
        "memo": "minimal",
        "letter": "corporate",
        "presentation": "creative",
        "spreadsheet": "minimal",
        "manual": "tech",
        "policy": "government",
        "analysis": "tech",
        "plan": "corporate",
        "summary": "minimal",
        "certificate": "government",
    }

    # 受众 → 主题调整
    AUDIENCE_ADJUSTMENTS = {
        "executive": {"color_accent_opacity": 0.8, "font_size_scale": 1.1},
        "technical": {"font_code_highlight": True, "spacing_section_gap": 1.2},
        "client": {"color_warmth": 0.2},
        "government": {"force_theme": "government"},
    }

    def __init__(self, config_dir: Optional[str] = None):
        self.themes: Dict[str, DocumentTheme] = {}
        self.config_dir = config_dir
        self._load_themes()

    def _load_themes(self):
        """加载所有可用主题"""
        # 加载预设主题
        for theme_id in DocumentTheme.PRESETS:
            self.themes[theme_id] = DocumentTheme(theme_id)

        # 加载自定义主题 (从配置目录)
        if self.config_dir:
            config_path = Path(self.config_dir) / "office_themes.json"
            if config_path.exists():
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        custom_themes = json.load(f)
                        for tid, tdata in custom_themes.items():
                            # 简化处理: 用预设 + 覆盖
                            base = tdata.get("base", "corporate")
                            overrides = tdata.get("overrides", {})
                            self.themes[tid] = DocumentTheme(base, overrides)
                            self.themes[tid].name = tdata.get("name", tid)
                    logger.info(f"加载自定义主题: {list(custom_themes.keys())}")
                except Exception as e:
                    logger.warning(f"加载自定义主题失败: {e}")

    def get_theme(self, theme_id: str) -> DocumentTheme:
        """获取指定主题"""
        return self.themes.get(theme_id, self.themes["corporate"])

    def recommend_theme(self, document_type: str, audience: str = "general") -> str:
        """根据文档类型和受众推荐主题"""
        # 受客调整优先
        adj = self.AUDIENCE_ADJUSTMENTS.get(audience, {})
        if "force_theme" in adj:
            return adj["force_theme"]

        return self.TYPE_THEME_MAP.get(document_type, "corporate")

    def check_brand_compliance(self, theme: DocumentTheme, brand_rules: dict) -> List[dict]:
        """品牌合规检查"""
        issues = []

        # 检查品牌色
        brand_primary = brand_rules.get("brand_primary_color")
        if brand_primary:
            theme_primary = theme.get_color(ColorRole.PRIMARY)
            if theme_primary.upper() != brand_primary.upper():
                issues.append({
                    "level": "warning",
                    "field": "color.primary",
                    "expected": brand_primary,
                    "actual": theme_primary,
                    "message": f"主色与品牌色不一致: 期望 {brand_primary}, 实际 {theme_primary}",
                })

        # 检查品牌字体
        brand_font = brand_rules.get("brand_heading_font")
        if brand_font:
            theme_font = theme.get_font(FontRole.HEADING_1)
            if theme_font.family != brand_font:
                issues.append({
                    "level": "warning",
                    "field": "font.heading_1",
                    "expected": brand_font,
                    "actual": theme_font.family,
                    "message": f"标题字体与品牌规范不一致",
                })

        return issues

    def list_themes(self) -> List[dict]:
        """列出所有可用主题"""
        return [
            {"id": tid, "name": t.name, "colors": len(t.colors)}
            for tid, t in self.themes.items()
        ]
