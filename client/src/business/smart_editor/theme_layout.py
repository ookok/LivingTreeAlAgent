"""
Theme and Layout System - 主题和布局系统
=====================================

提供统一的UI主题和响应式布局支持

特性:
- 预设主题 (dark/light/nature)
- 自定义主题
- 响应式布局 (desktop/tablet/mobile)
- CSS生成
"""

import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from enum import Enum


class ThemeType(Enum):
    """主题类型"""
    DARK = "dark"
    LIGHT = "light"
    NATURE = "nature"


class LayoutType(Enum):
    """布局类型"""
    DESKTOP = "desktop"     # 桌面 (>= 1200px)
    TABLET = "tablet"      # 平板 (768-1200px)
    MOBILE = "mobile"      # 手机 (< 768px)


@dataclass
class ThemeColors:
    """主题颜色"""
    # 背景
    bg_primary: str = "#1e1e1e"
    bg_secondary: str = "#252526"
    bg_tertiary: str = "#2d2d2d"
    bg_hover: str = "#3c3c3c"
    bg_active: str = "#4c4c4c"

    # 文字
    text_primary: str = "#d4d4d4"
    text_secondary: str = "#858585"
    text_disabled: str = "#5a5a5a"

    # 边框
    border: str = "#3c3c3c"
    border_focus: str = "#007acc"

    # 主题色
    primary: str = "#007acc"
    primary_hover: str = "#1e90ff"
    secondary: str = "#3794ff"

    # 状态色
    success: str = "#4CAF50"
    warning: str = "#ff9800"
    error: str = "#f44336"
    info: str = "#2196F3"

    # 编辑器特定
    line_number: str = "#858585"
    selection_bg: str = "#264f78"
    current_line_bg: str = "#2a2d2e"
    cursor: str = "#aeafad"
    whitespace: str = "#3c3c3c"


@dataclass
class EditorTheme:
    """编辑器主题"""
    name: str
    type: ThemeType
    colors: ThemeColors
    font_family: str = "Consolas, 'Courier New', monospace"
    font_size: int = 14
    line_height: float = 1.5
    tab_size: int = 4


@dataclass
class LayoutConfig:
    """布局配置"""
    layout_type: LayoutType = LayoutType.DESKTOP
    width: int = 1200
    height: int = 800

    # 侧边栏
    sidebar_width: int = 300
    sidebar_collapsible: bool = True
    sidebar_position: str = "right"  # left/right

    # AI面板
    ai_panel_visible: bool = True
    ai_panel_width: int = 350
    ai_panel_position: str = "right"  # bottom/right

    # 工具栏
    toolbar_visible: bool = True
    toolbar_position: str = "top"  # top/bottom

    # 预览面板
    preview_visible: bool = False
    preview_position: str = "right"  # bottom/right

    # 图标网格
    grid_columns: int = 6
    icon_size: int = 48

    def __post_init__(self):
        self._update_for_layout_type()

    def _update_for_layout_type(self):
        """根据布局类型更新配置"""
        if self.layout_type == LayoutType.MOBILE:
            self.sidebar_width = 0
            self.sidebar_collapsible = True
            self.ai_panel_width = 0
            self.ai_panel_visible = False
            self.preview_visible = False
            self.grid_columns = 3
            self.icon_size = 56
        elif self.layout_type == LayoutType.TABLET:
            self.sidebar_width = 250
            self.ai_panel_width = 300
            self.preview_visible = True
            self.grid_columns = 5
            self.icon_size = 48


# 预设主题
PRESET_THEMES = {
    ThemeType.DARK: EditorTheme(
        name="深色主题",
        type=ThemeType.DARK,
        colors=ThemeColors(
            bg_primary="#1e1e1e",
            bg_secondary="#252526",
            bg_tertiary="#2d2d2e",
            bg_hover="#3c3c3c",
            bg_active="#4c4c4c",
            text_primary="#d4d4d4",
            text_secondary="#858585",
            text_disabled="#5a5a5a",
            border="#3c3c3c",
            border_focus="#007acc",
            primary="#007acc",
            primary_hover="#1e90ff",
            secondary="#3794ff",
            success="#4CAF50",
            warning="#ff9800",
            error="#f44336",
            info="#2196F3",
            line_number="#858585",
            selection_bg="#264f78",
            current_line_bg="#2a2d2e",
            cursor="#aeafad",
        )
    ),

    ThemeType.LIGHT: EditorTheme(
        name="浅色主题",
        type=ThemeType.LIGHT,
        colors=ThemeColors(
            bg_primary="#ffffff",
            bg_secondary="#f3f3f3",
            bg_tertiary="#e8e8e8",
            bg_hover="#e0e0e0",
            bg_active="#d0d0d0",
            text_primary="#333333",
            text_secondary="#666666",
            text_disabled="#999999",
            border="#d4d4d4",
            border_focus="#007acc",
            primary="#007acc",
            primary_hover="#1e90ff",
            secondary="#126eaf",
            success="#4CAF50",
            warning="#ff9800",
            error="#f44336",
            info="#2196F3",
            line_number="#237893",
            selection_bg="#add6ff",
            current_line_bg="#f3f3f3",
            cursor="#000000",
            whitespace="#f8f8f8",
        )
    ),

    ThemeType.NATURE: EditorTheme(
        name="自然主题",
        type=ThemeType.NATURE,
        colors=ThemeColors(
            bg_primary="#1a2f1a",
            bg_secondary="#243524",
            bg_tertiary="#2d4a2d",
            bg_hover="#3a5a3a",
            bg_active="#4a6a4a",
            text_primary="#c8e6c8",
            text_secondary="#8fbc8f",
            text_disabled="#556b55",
            border="#3a5a3a",
            border_focus="#6aaa6a",
            primary="#6aaa6a",
            primary_hover="#7cba7c",
            secondary="#5a9a5a",
            success="#8fbc8f",
            warning="#d4a574",
            error="#cd5c5c",
            info="#6aaa6a",
            line_number="#6a8a6a",
            selection_bg="#3a5a3a",
            current_line_bg="#243524",
            cursor="#c8e6c8",
        )
    ),
}


class ThemeSystem:
    """
    主题系统

    管理编辑器的视觉主题和布局
    """

    def __init__(self):
        self.current_theme: EditorTheme = PRESET_THEMES[ThemeType.DARK]
        self.custom_themes: Dict[str, EditorTheme] = {}
        self._on_theme_change: Optional[Callable] = None

    def set_theme(self, theme_type: ThemeType | str):
        """设置主题"""
        if isinstance(theme_type, str):
            theme_type = ThemeType(theme_type)

        if theme_type in PRESET_THEMES:
            self.current_theme = PRESET_THEMES[theme_type]
        elif theme_type in self.custom_themes:
            self.current_theme = self.custom_themes[theme_type]
        else:
            raise ValueError(f"Unknown theme: {theme_type}")

        if self._on_theme_change:
            self._on_theme_change(self.current_theme)

    def register_custom_theme(self, theme: EditorTheme):
        """注册自定义主题"""
        self.custom_themes[theme.name] = theme

    def get_available_themes(self) -> List[str]:
        """获取可用主题列表"""
        themes = [t.name for t in PRESET_THEMES.values()]
        themes.extend(list(self.custom_themes.keys()))
        return themes

    def generate_css(self) -> str:
        """生成CSS变量"""
        c = self.current_theme.colors
        t = self.current_theme

        return f"""
:root {{
    /* 背景 */
    --editor-bg-primary: {c.bg_primary};
    --editor-bg-secondary: {c.bg_secondary};
    --editor-bg-tertiary: {c.bg_tertiary};
    --editor-bg-hover: {c.bg_hover};
    --editor-bg-active: {c.bg_active};

    /* 文字 */
    --editor-text-primary: {c.text_primary};
    --editor-text-secondary: {c.text_secondary};
    --editor-text-disabled: {c.text_disabled};

    /* 边框 */
    --editor-border: {c.border};
    --editor-border-focus: {c.border_focus};

    /* 主题色 */
    --editor-primary: {c.primary};
    --editor-primary-hover: {c.primary_hover};
    --editor-secondary: {c.secondary};

    /* 状态色 */
    --editor-success: {c.success};
    --editor-warning: {c.warning};
    --editor-error: {c.error};
    --editor-info: {c.info};

    /* 编辑器特定 */
    --editor-line-number: {c.line_number};
    --editor-selection-bg: {c.selection_bg};
    --editor-current-line-bg: {c.current_line_bg};
    --editor-cursor: {c.cursor};
    --editor-whitespace: {c.whitespace};

    /* 字体 */
    --editor-font-family: {t.font_family};
    --editor-font-size: {t.font_size}px;
    --editor-line-height: {t.line_height};
    --editor-tab-size: {t.tab_size};
}}
"""

    def generate_editor_styles(self) -> str:
        """生成编辑器样式"""
        css = self.generate_css()
        return css + """
/* 编辑器容器 */
.smart-editor {{
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--editor-bg-primary);
    color: var(--editor-text-primary);
    font-family: var(--editor-font-family);
    font-size: var(--editor-font-size);
    line-height: var(--editor-line-height);
}}

/* 工具栏 */
.editor-toolbar {{
    display: flex;
    align-items: center;
    padding: 8px 12px;
    background: var(--editor-bg-secondary);
    border-bottom: 1px solid var(--editor-border);
    gap: 8px;
}}

.editor-toolbar button {{
    padding: 6px 12px;
    background: var(--editor-bg-tertiary);
    border: 1px solid var(--editor-border);
    border-radius: 4px;
    color: var(--editor-text-primary);
    cursor: pointer;
    font-size: 12px;
    transition: all 0.2s;
}}

.editor-toolbar button:hover {{
    background: var(--editor-bg-hover);
    border-color: var(--editor-primary);
}}

.editor-toolbar button.active {{
    background: var(--editor-primary);
    border-color: var(--editor-primary);
    color: white;
}}

/* AI操作按钮 */
.ai-button {{
    background: linear-gradient(135deg, var(--editor-primary), var(--editor-secondary)) !important;
}}

.ai-button:hover {{
    background: var(--editor-primary-hover) !important;
}}

/* 编辑区域 */
.editor-content {{
    flex: 1;
    display: flex;
    overflow: hidden;
}}

/* 行号区域 */
.line-numbers {{
    padding: 8px 12px;
    background: var(--editor-bg-secondary);
    color: var(--editor-line-number);
    text-align: right;
    user-select: none;
    font-size: 13px;
    min-width: 50px;
    border-right: 1px solid var(--editor-border);
}}

/* 文本编辑区 */
.text-area {{
    flex: 1;
    padding: 8px;
    background: var(--editor-bg-primary);
    color: var(--editor-text-primary);
    border: none;
    outline: none;
    resize: none;
    font-family: var(--editor-font-family);
    font-size: var(--editor-font-size);
    line-height: var(--editor-line-height);
    tab-size: var(--editor-tab-size);
}}

.text-area::selection {{
    background: var(--editor-selection-bg);
}}

/* 当前行高亮 */
.text-area .current-line {{
    background: var(--editor-current-line-bg);
}}

/* AI面板 */
.ai-panel {{
    width: 350px;
    background: var(--editor-bg-secondary);
    border-left: 1px solid var(--editor-border);
    display: flex;
    flex-direction: column;
}}

.ai-panel-header {{
    padding: 12px 16px;
    border-bottom: 1px solid var(--editor-border);
    font-weight: bold;
}}

.ai-panel-content {{
    flex: 1;
    padding: 12px;
    overflow-y: auto;
}}

/* 补全下拉框 */
.completion-dropdown {{
    position: absolute;
    background: var(--editor-bg-secondary);
    border: 1px solid var(--editor-border);
    border-radius: 4px;
    max-height: 300px;
    overflow-y: auto;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}}

.completion-item {{
    padding: 8px 12px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
}}

.completion-item:hover {{
    background: var(--editor-bg-hover);
}}

.completion-item.selected {{
    background: var(--editor-primary);
    color: white;
}}

.completion-kind {{
    font-size: 10px;
    padding: 2px 6px;
    background: var(--editor-bg-tertiary);
    border-radius: 3px;
    color: var(--editor-text-secondary);
}}

/* 语法高亮 */
.syntax-heading {{ color: var(--editor-primary); }}
.syntax-keyword {{ color: #569cd6; }}
.syntax-string {{ color: #ce9178; }}
.syntax-comment {{ color: #6a9955; }}
.syntax-number {{ color: #b5cea8; }}
.syntax-function {{ color: #dcdcaa; }}
.syntax-type {{ color: #4ec9b0; }}
.syntax-variable {{ color: #9cdcfe; }}
.syntax-operator {{ color: #d4d4d4; }}

/* 状态栏 */
.status-bar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 12px;
    background: var(--editor-bg-secondary);
    border-top: 1px solid var(--editor-border);
    font-size: 12px;
    color: var(--editor-text-secondary);
}}

.status-item {{
    display: flex;
    align-items: center;
    gap: 4px;
}}

/* 快捷键提示 */
.shortcut-hint {{
    position: absolute;
    right: 8px;
    font-size: 11px;
    color: var(--editor-text-secondary);
    background: var(--editor-bg-tertiary);
    padding: 2px 6px;
    border-radius: 3px;
}}

/* 动画 */
@keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(-4px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}

.fade-in {{
    animation: fadeIn 0.2s ease-out;
}}

@keyframes shake {{
    0%, 100% {{ transform: translateX(0); }}
    25% {{ transform: translateX(-2px); }}
    75% {{ transform: translateX(2px); }}
}}

.icon-shake {{
    animation: shake 0.3s ease-in-out;
}}
"""

    def on_theme_change(self, callback: Callable):
        """主题变化回调"""
        self._on_theme_change = callback


class LayoutManager:
    """
    布局管理器

    管理响应式布局和窗口配置
    """

    def __init__(self):
        self.config = LayoutConfig()
        self._on_layout_change: Optional[Callable] = None

    def detect_layout_type(self, width: int, height: int) -> LayoutType:
        """检测布局类型"""
        if width < 768:
            return LayoutType.MOBILE
        elif width < 1200:
            return LayoutType.TABLET
        else:
            return LayoutType.DESKTOP

    def update_size(self, width: int, height: int):
        """更新窗口大小"""
        self.config.width = width
        self.config.height = height
        new_type = self.detect_layout_type(width, height)

        if new_type != self.config.layout_type:
            old_type = self.config.layout_type
            self.config.layout_type = new_type
            self.config._update_for_layout_type()

            if self._on_layout_change:
                self._on_layout_change(old_type, new_type, self.config)

    def set_layout_type(self, layout_type: LayoutType):
        """设置布局类型"""
        if layout_type != self.config.layout_type:
            old_type = self.config.layout_type
            self.config.layout_type = layout_type
            self.config._update_for_layout_type()

            if self._on_layout_change:
                self._on_layout_change(old_type, layout_type, self.config)

    def is_sidebar_visible(self) -> bool:
        """侧边栏是否可见"""
        return self.config.sidebar_width > 0 and self.config.sidebar_collapsible

    def is_ai_panel_visible(self) -> bool:
        """AI面板是否可见"""
        return self.config.ai_panel_visible and self.config.ai_panel_width > 0

    def toggle_sidebar(self):
        """切换侧边栏"""
        if self.config.sidebar_collapsible:
            if self.config.sidebar_width > 0:
                self.config.sidebar_width = 0
            else:
                self.config.sidebar_width = 300

    def toggle_ai_panel(self):
        """切换AI面板"""
        if self.config.ai_panel_visible:
            self.config.ai_panel_width = 0
            self.config.ai_panel_visible = False
        else:
            self.config.ai_panel_width = 350
            self.config.ai_panel_visible = True

    def toggle_preview(self):
        """切换预览面板"""
        self.config.preview_visible = not self.config.preview_visible

    def on_layout_change(self, callback: Callable):
        """布局变化回调"""
        self._on_layout_change = callback

    def to_dict(self) -> Dict[str, Any]:
        """导出配置"""
        return {
            'layout_type': self.config.layout_type.value,
            'width': self.config.width,
            'height': self.config.height,
            'sidebar_width': self.config.sidebar_width,
            'ai_panel_visible': self.config.ai_panel_visible,
            'ai_panel_width': self.config.ai_panel_width,
            'preview_visible': self.config.preview_visible,
            'grid_columns': self.config.grid_columns,
            'icon_size': self.config.icon_size,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LayoutManager':
        """从配置创建"""
        manager = cls()
        if 'layout_type' in data:
            manager.config.layout_type = LayoutType(data['layout_type'])
        if 'sidebar_width' in data:
            manager.config.sidebar_width = data['sidebar_width']
        if 'ai_panel_visible' in data:
            manager.config.ai_panel_visible = data['ai_panel_visible']
        if 'ai_panel_width' in data:
            manager.config.ai_panel_width = data['ai_panel_width']
        if 'preview_visible' in data:
            manager.config.preview_visible = data['preview_visible']
        if 'grid_columns' in data:
            manager.config.grid_columns = data['grid_columns']
        if 'icon_size' in data:
            manager.config.icon_size = data['icon_size']
        return manager


# 全局实例
_global_theme_system: Optional[ThemeSystem] = None
_global_layout_manager: Optional[LayoutManager] = None


def get_theme_system() -> ThemeSystem:
    """获取全局主题系统"""
    global _global_theme_system
    if _global_theme_system is None:
        _global_theme_system = ThemeSystem()
    return _global_theme_system


def get_layout_manager() -> LayoutManager:
    """获取全局布局管理器"""
    global _global_layout_manager
    if _global_layout_manager is None:
        _global_layout_manager = LayoutManager()
    return _global_layout_manager