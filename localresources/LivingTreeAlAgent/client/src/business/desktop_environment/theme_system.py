# theme_system.py — 主题系统
# ============================================================================
#
# 负责桌面主题、颜色方案、动画配置的管理
# 支持动态壁纸、自定义主题
#
# ============================================================================

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from pathlib import Path
from enum import Enum

# ============================================================================
# 主题数据结构
# ============================================================================

@dataclass
class ThemeColors:
    """主题颜色"""
    # 主色
    primary: str = "#4A90D9"
    primary_dark: str = "#357ABD"
    primary_light: str = "#6BA3E0"

    # 次要色
    secondary: str = "#50C878"
    secondary_dark: str = "#3DA668"
    secondary_light: str = "#6DD492"

    # 背景色
    background: str = "#1E1E1E"
    background_light: str = "#2D2D2D"
    surface: str = "#252525"

    # 文字色
    text_primary: str = "#FFFFFF"
    text_secondary: str = "#B0B0B0"
    text_disabled: str = "#606060"

    # 状态色
    success: str = "#4CAF50"
    warning: str = "#FF9800"
    error: str = "#F44336"
    info: str = "#2196F3"

    # 边框
    border: str = "#3D3D3D"
    border_light: str = "#4D4D4D"

    # 特殊
    shadow: str = "#000000"
    overlay: str = "rgba(0, 0, 0, 0.5)"
    gradient_start: str = "#4A90D9"
    gradient_end: str = "#357ABD"

@dataclass
class AnimationConfig:
    """动画配置"""
    enabled: bool = True
    duration_fast: float = 0.15  # 秒
    duration_normal: float = 0.3
    duration_slow: float = 0.5

    # 窗口动画
    window_open: str = "zoom"    # zoom, fade, slide, pop
    window_close: str = "fade"
    window_minimize: str = "fade"

    # 图标动画
    icon_hover: str = "scale"
    icon_click: str = "bounce"
    icon_drag: str = "lift"

    # 过渡动画
    page_transition: str = "slide"
    dialog_open: str = "pop"

@dataclass
class Theme:
    """完整主题"""
    id: str
    name: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""

    # 颜色
    colors: ThemeColors = field(default_factory=ThemeColors)

    # 动画
    animation: AnimationConfig = field(default_factory=AnimationConfig)

    # 壁纸
    wallpaper: str = ""
    wallpaper_mode: str = "fit"  # stretch, fit, fill, tile, center

    # 图标
    icon_size: int = 64
    icon_pack: str = "default"

    # 字体
    font_family: str = "Segoe UI, Microsoft YaHei, sans-serif"
    font_size_base: int = 14

    # 圆角
    border_radius_small: int = 4
    border_radius_medium: int = 8
    border_radius_large: int = 12

    # 阴影
    shadow_enabled: bool = True
    shadow_blur: int = 10
    shadow_offset: int = 4

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "colors": self.colors.__dict__,
            "animation": self.animation.__dict__,
            "wallpaper": self.wallpaper,
            "wallpaper_mode": self.wallpaper_mode,
            "icon_size": self.icon_size,
            "icon_pack": self.icon_pack,
            "font_family": self.font_family,
            "font_size_base": self.font_size_base,
            "border_radius_small": self.border_radius_small,
            "border_radius_medium": self.border_radius_medium,
            "border_radius_large": self.border_radius_large,
            "shadow_enabled": self.shadow_enabled,
            "shadow_blur": self.shadow_blur,
            "shadow_offset": self.shadow_offset,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Theme":
        data = data.copy()
        data["colors"] = ThemeColors(**data.get("colors", {}))
        data["animation"] = AnimationConfig(**data.get("animation", {}))
        return cls(**data)

# ============================================================================
# 预设主题
# ============================================================================

LIGHT_THEME = Theme(
    id="light",
    name="浅色主题",
    description="明亮的浅色主题",
    colors=ThemeColors(
        primary="#4A90D9",
        primary_dark="#357ABD",
        primary_light="#6BA3E0",
        secondary="#50C878",
        background="#F5F5F5",
        background_light="#FFFFFF",
        surface="#FFFFFF",
        text_primary="#1A1A1A",
        text_secondary="#666666",
        text_disabled="#999999",
        border="#E0E0E0",
        border_light="#EEEEEE",
    ),
    wallpaper="",
    wallpaper_mode="fit",
)

DARK_THEME = Theme(
    id="dark",
    name="深色主题",
    description="护眼的深色主题",
    colors=ThemeColors(
        primary="#4A90D9",
        primary_dark="#357ABD",
        primary_light="#6BA3E0",
        secondary="#50C878",
        background="#1E1E1E",
        background_light="#2D2D2D",
        surface="#252525",
        text_primary="#FFFFFF",
        text_secondary="#B0B0B0",
        text_disabled="#606060",
        border="#3D3D3D",
        border_light="#4D4D4D",
    ),
    wallpaper="",
    wallpaper_mode="fit",
)

NATURE_THEME = Theme(
    id="nature",
    name="自然主题",
    description="清新自然的绿色主题",
    colors=ThemeColors(
        primary="#2E7D32",
        primary_dark="#1B5E20",
        primary_light="#4CAF50",
        secondary="#8BC34A",
        background="#E8F5E9",
        background_light="#F1F8E9",
        surface="#FFFFFF",
        text_primary="#1A1A1A",
        text_secondary="#555555",
        gradient_start="#4CAF50",
        gradient_end="#2E7D32",
    ),
    wallpaper="nature_wallpaper.jpg",
    wallpaper_mode="fill",
)

# ============================================================================
# 主题系统
# ============================================================================

class ThemeSystem:
    """
    主题系统

    职责:
    1. 管理主题 (加载、保存、切换)
    2. 提供主题 CSS 样式生成
    3. 管理动态壁纸
    4. 主题预览
    """

    def __init__(self):
        self._themes: Dict[str, Theme] = {}
        self._current_theme: Theme = DARK_THEME
        self._is_dark_mode: bool = True

        # 回调
        self._on_theme_changed: Optional[Callable] = None

        # 初始化预设主题
        self._register_preset_themes()

    # --------------------------------------------------------------------------
    # 主题管理
    # --------------------------------------------------------------------------

    def register_theme(self, theme: Theme) -> bool:
        """注册主题"""
        if theme.id in self._themes:
            return False
        self._themes[theme.id] = theme
        return True

    def unregister_theme(self, theme_id: str) -> bool:
        """注销主题"""
        if theme_id in ["light", "dark", "nature"]:
            return False  # 不能注销预设主题
        if theme_id in self._themes:
            self._themes.pop(theme_id)
            return True
        return False

    def get_theme(self, theme_id: str) -> Optional[Theme]:
        """获取主题"""
        return self._themes.get(theme_id)

    def get_all_themes(self) -> List[Theme]:
        """获取所有主题"""
        return list(self._themes.values())

    def get_current_theme(self) -> Theme:
        """获取当前主题"""
        return self._current_theme

    def set_theme(self, theme_id: str) -> bool:
        """设置当前主题"""
        theme = self._themes.get(theme_id)
        if not theme:
            return False

        self._current_theme = theme
        self._is_dark_mode = self._is_dark(theme)

        if self._on_theme_changed:
            self._on_theme_changed(theme)

        return True

    def _is_dark(self, theme: Theme) -> bool:
        """判断是否为深色主题"""
        # 简单判断背景亮度
        bg = theme.colors.background
        if bg.startswith("#"):
            r = int(bg[1:3], 16)
            g = int(bg[3:5], 16)
            b = int(bg[5:7], 16)
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            return brightness < 128
        return False

    def _register_preset_themes(self):
        """注册预设主题"""
        self._themes = {
            "light": LIGHT_THEME,
            "dark": DARK_THEME,
            "nature": NATURE_THEME,
        }

    # --------------------------------------------------------------------------
    # 主题应用
    # --------------------------------------------------------------------------

    def generate_css(self) -> str:
        """生成 CSS 样式"""
        theme = self._current_theme
        colors = theme.colors
        anim = theme.animation

        css = f"""
:root {{
    /* 主色 */
    --primary: {colors.primary};
    --primary-dark: {colors.primary_dark};
    --primary-light: {colors.primary_light};

    /* 次要色 */
    --secondary: {colors.secondary};
    --secondary-dark: {colors.secondary_dark};
    --secondary-light: {colors.secondary_light};

    /* 背景 */
    --background: {colors.background};
    --background-light: {colors.background_light};
    --surface: {colors.surface};

    /* 文字 */
    --text-primary: {colors.text_primary};
    --text-secondary: {colors.text_secondary};
    --text-disabled: {colors.text_disabled};

    /* 状态 */
    --success: {colors.success};
    --warning: {colors.warning};
    --error: {colors.error};
    --info: {colors.info};

    /* 边框 */
    --border: {colors.border};
    --border-light: {colors.border_light};

    /* 特殊 */
    --shadow: {colors.shadow};
    --overlay: {colors.overlay};
    --gradient-start: {colors.gradient_start};
    --gradient-end: {colors.gradient_end};

    /* 字体 */
    --font-family: {theme.font_family};
    --font-size-base: {theme.font_size_base}px;

    /* 圆角 */
    --radius-small: {theme.border_radius_small}px;
    --radius-medium: {theme.border_radius_medium}px;
    --radius-large: {theme.border_radius_large}px;

    /* 阴影 */
    --shadow-blur: {theme.shadow_blur}px;
    --shadow-offset: {theme.shadow_offset}px;
}}

/* 动画 */
.animated {{
    transition: all {anim.duration_normal}s ease;
}}

.animated-fast {{
    transition: all {anim.duration_fast}s ease;
}}

.animated-slow {{
    transition: all {anim.duration_slow}s ease;
}}

/* 窗口 */
.window {{
    background: var(--surface);
    border-radius: var(--radius-large);
    box-shadow: 0 var(--shadow-offset) var(--shadow-blur) var(--shadow);
}}

/* 标题栏 */
.title-bar {{
    background: var(--background-light);
    border-bottom: 1px solid var(--border);
}}

/* 桌面图标 */
.desktop-icon {{
    width: {theme.icon_size}px;
    height: {theme.icon_size}px;
}}

/* 任务栏 */
.taskbar {{
    background: var(--surface);
    border-top: 1px solid var(--border);
}}
"""

        return css

    def get_wallpaper(self) -> str:
        """获取壁纸路径"""
        return self._current_theme.wallpaper

    def get_wallpaper_mode(self) -> str:
        """获取壁纸模式"""
        return self._current_theme.wallpaper_mode

    def is_dark_mode(self) -> bool:
        """是否为深色模式"""
        return self._is_dark_mode

    # --------------------------------------------------------------------------
    # 动态壁纸
    # --------------------------------------------------------------------------

    def set_live_wallpaper(self, wallpaper_id: str):
        """设置动态壁纸"""
        self._current_theme.wallpaper = wallpaper_id
        # 实现动态壁纸逻辑
        # 可能需要启动一个后台进程来播放视频/动图

    # --------------------------------------------------------------------------
    # 主题导入导出
    # --------------------------------------------------------------------------

    def export_theme(self, theme_id: str, file_path: Path) -> bool:
        """导出主题到文件"""
        theme = self._themes.get(theme_id)
        if not theme:
            return False

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(theme.to_dict(), f, ensure_ascii=False, indent=2)

        return True

    def import_theme(self, file_path: Path) -> Optional[Theme]:
        """从文件导入主题"""
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        theme = Theme.from_dict(data)

        # 生成新 ID 避免冲突
        import uuid
        theme.id = f"{theme.id}_{uuid.uuid4().hex[:8]}"

        self.register_theme(theme)
        return theme

    # --------------------------------------------------------------------------
    # 持久化
    # --------------------------------------------------------------------------

    def load_settings(self):
        """加载主题设置"""
        from . import _DATA_DIR
        settings_file = _DATA_DIR / "theme_settings.json"

        if settings_file.exists():
            try:
                with open(settings_file, encoding="utf-8") as f:
                    data = json.load(f)
                    current_id = data.get("current_theme")
                    if current_id and current_id in self._themes:
                        self._current_theme = self._themes[current_id]
            except Exception as e:
                print(f"Failed to load theme settings: {e}")

    def save_settings(self):
        """保存主题设置"""
        from . import _DATA_DIR
        settings_file = _DATA_DIR / "theme_settings.json"

        data = {
            "current_theme": self._current_theme.id,
        }

        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # --------------------------------------------------------------------------
    # 事件
    # --------------------------------------------------------------------------

    def set_on_theme_changed(self, callback: Callable[[Theme], None]):
        """设置主题变更回调"""
        self._on_theme_changed = callback

# ============================================================================
# 全局访问器
# ============================================================================

_theme_system_instance: Optional[ThemeSystem] = None

def get_theme_system() -> ThemeSystem:
    """获取全局 ThemeSystem 实例"""
    global _theme_system_instance
    if _theme_system_instance is None:
        _theme_system_instance = ThemeSystem()
    return _theme_system_instance