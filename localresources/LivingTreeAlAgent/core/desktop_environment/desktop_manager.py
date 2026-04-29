# desktop_manager.py — 桌面管理器
# ============================================================================
#
# 负责管理桌面环境的核心组件
# 包括壁纸、图标网格、桌面布局、背景设置等
#
# ============================================================================

import json
import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from pathlib import Path
from enum import Enum

# ============================================================================
# 配置与枚举
# ============================================================================

class WallpaperMode(Enum):
    """壁纸模式"""
    STRETCH = "stretch"           # 拉伸
    FIT = "fit"                   # 自适应
    FILL = "fill"                # 填充
    TILE = "tile"                # 平铺
    CENTER = "center"             # 居中
    DYNAMIC = "dynamic"          # 动态壁纸

class GridLayout(Enum):
    """网格布局"""
    FREE = "free"                 # 自由布局
    GRID = "grid"                # 网格对齐
    AUTO = "auto"                # 自动排列

@dataclass
class DesktopConfig:
    """桌面配置"""
    # 壁纸
    wallpaper_path: str = ""
    wallpaper_mode: WallpaperMode = WallpaperMode.FIT

    # 图标网格
    grid_columns: int = 6
    grid_rows: int = 4
    icon_size: int = 64
    icon_spacing: int = 16
    grid_layout: GridLayout = GridLayout.AUTO

    # 行为
    show_desktop_icons: bool = True
    enable_drag: bool = True
    enable_double_click: bool = True
    enable_context_menu: bool = True

    # 多桌面
    desktop_count: int = 3
    current_desktop: int = 0

    # 动画
    enable_animations: bool = True
    animation_duration: float = 0.3

    @classmethod
    def load(cls, config_file: Path) -> "DesktopConfig":
        """从文件加载配置"""
        if config_file.exists():
            with open(config_file, encoding="utf-8") as f:
                data = json.load(f)
                data["wallpaper_mode"] = WallpaperMode(data.get("wallpaper_mode", "fit"))
                data["grid_layout"] = GridLayout(data.get("grid_layout", "auto"))
                return cls(**data)
        return cls()

    def save(self, config_file: Path):
        """保存配置到文件"""
        data = {
            "wallpaper_path": self.wallpaper_path,
            "wallpaper_mode": self.wallpaper_mode.value,
            "grid_columns": self.grid_columns,
            "grid_rows": self.grid_rows,
            "icon_size": self.icon_size,
            "icon_spacing": self.icon_spacing,
            "grid_layout": self.grid_layout.value,
            "show_desktop_icons": self.show_desktop_icons,
            "enable_drag": self.enable_drag,
            "enable_double_click": self.enable_double_click,
            "enable_context_menu": self.enable_context_menu,
            "desktop_count": self.desktop_count,
            "current_desktop": self.current_desktop,
            "enable_animations": self.enable_animations,
            "animation_duration": self.animation_duration,
        }
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# ============================================================================
# 桌面管理器
# ============================================================================

class DesktopManager:
    """
    桌面管理器

    职责:
    1. 管理桌面壁纸和背景
    2. 管理桌面图标网格布局
    3. 处理桌面级别的交互事件
    4. 管理多桌面切换
    """

    def __init__(self, config: DesktopConfig = None):
        self.config = config or DesktopConfig()

        # 状态
        self._icons: Dict[str, "DesktopIcon"] = {}
        self._wallpaper: Optional[str] = None
        self._current_desktop: int = 0
        self._is_edit_mode: bool = False  # 编辑模式 (图标抖动)

        # 布局
        self._icon_positions: Dict[str, tuple] = {}  # icon_id -> (row, col)
        self._free_positions: List[tuple] = []  # 可用的 (row, col) 位置

        # 回调
        self._on_icon_double_click: Optional[Callable] = None
        self._on_icon_drag: Optional[Callable] = None
        self._on_desktop_click: Optional[Callable] = None
        self._on_context_menu: Optional[Callable] = None

        # 初始化
        self._initialize_grid()
        self._load_positions()

    # --------------------------------------------------------------------------
    # 桌面图标管理
    # --------------------------------------------------------------------------

    def register_icon(self, icon: "DesktopIcon") -> bool:
        """
        注册桌面图标

        Args:
            icon: DesktopIcon 实例

        Returns:
            bool: 是否注册成功
        """
        if icon.icon_id in self._icons:
            return False

        # 分配位置
        position = self._allocate_position()
        if position is None:
            return False

        self._icon_positions[icon.icon_id] = position
        icon.set_position(position[0], position[1])
        self._icons[icon.icon_id] = icon

        self._save_positions()
        return True

    def unregister_icon(self, icon_id: str) -> bool:
        """注销桌面图标"""
        if icon_id not in self._icons:
            return False

        # 释放位置
        position = self._icon_positions.pop(icon_id, None)
        if position:
            self._free_positions.append(position)

        # 移除图标
        self._icons.pop(icon_id)
        self._save_positions()
        return True

    def get_icon(self, icon_id: str) -> Optional["DesktopIcon"]:
        """获取桌面图标"""
        return self._icons.get(icon_id)

    def get_all_icons(self) -> List["DesktopIcon"]:
        """获取所有桌面图标"""
        return list(self._icons.values())

    def get_icons_by_desktop(self, desktop_index: int) -> List["DesktopIcon"]:
        """获取指定桌面的图标"""
        icons = []
        for icon in self._icons.values():
            if icon.desktop_index == desktop_index:
                icons.append(icon)
        return icons

    # --------------------------------------------------------------------------
    # 位置管理
    # --------------------------------------------------------------------------

    def _initialize_grid(self):
        """初始化网格"""
        self._free_positions = []
        for row in range(self.config.grid_rows):
            for col in range(self.config.grid_columns):
                self._free_positions.append((row, col))

    def _allocate_position(self) -> Optional[tuple]:
        """分配一个空闲位置"""
        if not self._free_positions:
            return None
        return self._free_positions.pop(0)

    def _release_position(self, row: int, col: int):
        """释放一个位置"""
        if (row, col) not in self._free_positions:
            self._free_positions.append((row, col))
            self._free_positions.sort()

    def move_icon(self, icon_id: str, new_row: int, new_col: int) -> bool:
        """移动图标到新位置"""
        if icon_id not in self._icons:
            return False

        old_position = self._icon_positions.get(icon_id)
        if old_position:
            self._release_position(old_position[0], old_position[1])

        self._icon_positions[icon_id] = (new_row, new_col)
        self._icons[icon_id].set_position(new_row, new_col)
        self._save_positions()
        return True

    def rearrange_icons(self):
        """重新排列所有图标"""
        self._free_positions = []
        for row in range(self.config.grid_rows):
            for col in range(self.config.grid_columns):
                self._free_positions.append((row, col))

        for icon_id, icon in self._icons.items():
            position = self._allocate_position()
            if position:
                self._icon_positions[icon_id] = position
                icon.set_position(position[0], position[1])

        self._save_positions()

    # --------------------------------------------------------------------------
    # 拖拽排序
    # --------------------------------------------------------------------------

    def start_drag(self, icon_id: str) -> bool:
        """开始拖拽图标"""
        if icon_id not in self._icons:
            return False
        self._icons[icon_id].start_drag()
        return True

    def drag_icon(self, icon_id: str, x: int, y: int):
        """拖拽图标"""
        if icon_id in self._icons:
            self._icons[icon_id].drag_to(x, y)

    def end_drag(self, icon_id: str) -> bool:
        """结束拖拽"""
        if icon_id not in self._icons:
            return False

        icon = self._icons[icon_id]
        icon.end_drag()

        # 计算新位置
        new_row = int(icon.y / (self.config.icon_size + self.config.icon_spacing))
        new_col = int(icon.x / (self.config.icon_size + self.config.icon_spacing))

        # 边界检查
        new_row = max(0, min(new_row, self.config.grid_rows - 1))
        new_col = max(0, min(new_col, self.config.grid_columns - 1))

        # 检查位置是否被占用
        occupied = self._find_icon_at(new_row, new_col)
        if occupied and occupied != icon_id:
            # 交换位置
            old_position = self._icon_positions.get(occupied)
            if old_position:
                self.move_icon(occupied, old_position[0], old_position[1])

        self.move_icon(icon_id, new_row, new_col)
        return True

    def _find_icon_at(self, row: int, col: int) -> Optional[str]:
        """查找指定位置的图标"""
        for icon_id, position in self._icon_positions.items():
            if position == (row, col):
                return icon_id
        return None

    # --------------------------------------------------------------------------
    # 编辑模式
    # --------------------------------------------------------------------------

    def enter_edit_mode(self):
        """进入编辑模式 (图标抖动)"""
        self._is_edit_mode = True
        for icon in self._icons.values():
            icon.start_wobble()

    def exit_edit_mode(self):
        """退出编辑模式"""
        self._is_edit_mode = False
        for icon in self._icons.values():
            icon.stop_wobble()

    def is_edit_mode(self) -> bool:
        """是否在编辑模式"""
        return self._is_edit_mode

    # --------------------------------------------------------------------------
    # 多桌面管理
    # --------------------------------------------------------------------------

    def switch_desktop(self, index: int) -> bool:
        """切换到指定桌面"""
        if 0 <= index < self.config.desktop_count:
            old_desktop = self._current_desktop
            self._current_desktop = index
            self.config.current_desktop = index
            return True
        return False

    def get_current_desktop(self) -> int:
        """获取当前桌面索引"""
        return self._current_desktop

    def get_desktop_count(self) -> int:
        """获取桌面数量"""
        return self.config.desktop_count

    # --------------------------------------------------------------------------
    # 壁纸管理
    # --------------------------------------------------------------------------

    def set_wallpaper(self, path: str, mode: WallpaperMode = None):
        """设置壁纸"""
        self.config.wallpaper_path = path
        if mode:
            self.config.wallpaper_mode = mode
        self._wallpaper = path
        self._save_config()

    def get_wallpaper(self) -> Optional[str]:
        """获取壁纸路径"""
        return self._wallpaper

    # --------------------------------------------------------------------------
    # 持久化
    # --------------------------------------------------------------------------

    def _get_config_file(self) -> Path:
        """获取配置文件路径"""
        from . import _DATA_DIR
        return _DATA_DIR / "desktop_config.json"

    def _get_positions_file(self) -> Path:
        """获取图标位置文件路径"""
        from . import _DATA_DIR
        return _DATA_DIR / "icon_positions.json"

    def _load_positions(self):
        """加载图标位置"""
        positions_file = self._get_positions_file()
        if positions_file.exists():
            with open(positions_file, encoding="utf-8") as f:
                self._icon_positions = json.load(f)

    def _save_positions(self):
        """保存图标位置"""
        positions_file = self._get_positions_file()
        with open(positions_file, "w", encoding="utf-8") as f:
            json.dump(self._icon_positions, f)

    def _save_config(self):
        """保存配置"""
        config_file = self._get_config_file()
        self.config.save(config_file)

    # --------------------------------------------------------------------------
    # 事件回调
    # --------------------------------------------------------------------------

    def set_on_icon_double_click(self, callback: Callable[["DesktopIcon"], None]):
        """设置图标双击回调"""
        self._on_icon_double_click = callback

    def set_on_icon_drag(self, callback: Callable[[str, int, int], None]):
        """设置图标拖拽回调"""
        self._on_icon_drag = callback

    def set_on_desktop_click(self, callback: Callable[[int, int], None]):
        """设置桌面点击回调"""
        self._on_desktop_click = callback

    def set_on_context_menu(self, callback: Callable[[int, int], None]):
        """设置右键菜单回调"""
        self._on_context_menu = callback

    # --------------------------------------------------------------------------
    # 响应式布局
    # --------------------------------------------------------------------------

    def calculate_grid_for_screen(self, screen_width: int, screen_height: int):
        """根据屏幕尺寸计算网格参数"""
        if screen_width < 600:      # 手机
            self.config.grid_columns = 3
            self.config.icon_size = 56
        elif screen_width < 1024:   # 平板
            self.config.grid_columns = 5
            self.config.icon_size = 72
        else:                       # 桌面
            self.config.grid_columns = 6
            self.config.icon_size = 84

        # 重新初始化网格
        self._initialize_grid()

    # --------------------------------------------------------------------------
    # 通知
    # --------------------------------------------------------------------------

    def notify_icon_double_click(self, icon: "DesktopIcon"):
        """通知图标被双击"""
        if self._on_icon_double_click:
            self._on_icon_double_click(icon)

    def notify_desktop_click(self, x: int, y: int):
        """通知桌面被点击"""
        if self._on_desktop_click:
            self._on_desktop_click(x, y)

    def notify_context_menu(self, x: int, y: int):
        """通知右键菜单"""
        if self._on_context_menu:
            self._on_context_menu(x, y)

# ============================================================================
# 全局访问器
# ============================================================================

_desktop_manager_instance: Optional[DesktopManager] = None

def get_desktop_manager() -> DesktopManager:
    """获取全局 DesktopManager 实例"""
    global _desktop_manager_instance
    if _desktop_manager_instance is None:
        _desktop_manager_instance = DesktopManager()
    return _desktop_manager_instance