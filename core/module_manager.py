"""
模块管理器
支持首页各模块的显示/隐藏配置
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from enum import Enum


class ModuleType(Enum):
    """模块类型"""
    RECOMMENDATION = "recommendation"    # 首页推荐
    GAME_HALL = "game_hall"             # 游戏世界
    RESEARCH = "research"               # 研究助手
    WRITING = "writing"                 # 写作助手


@dataclass
class ModuleConfig:
    """模块配置"""
    module_id: str
    name: str                           # 显示名称
    icon: str = "📦"                    # 图标
    enabled: bool = True                # 是否启用
    visible: bool = True                # 是否显示
    order: int = 0                      # 排序顺序
    description: str = ""                # 模块描述
    
    # 特殊配置
    auto_refresh: bool = False          # 是否自动刷新
    refresh_interval: int = 300         # 刷新间隔（秒）
    
    # 存储路径
    storage_key: str = ""               # 持久化数据的key


@dataclass
class ModuleState:
    """模块运行时状态"""
    module_id: str
    active: bool = False                # 是否活跃（正在使用）
    last_used: float = 0                 # 上次使用时间


class ModuleManager:
    """
    模块管理器
    负责管理所有首页模块的显示/隐藏配置
    """
    
    DEFAULT_MODULES = [
        ModuleConfig(
            module_id="recommendation",
            name="首页推荐",
            icon="🏠",
            enabled=True,
            visible=True,
            order=1,
            description="个性化内容推荐",
            auto_refresh=True,
            refresh_interval=300,
        ),
        ModuleConfig(
            module_id="game_hall",
            name="游戏世界",
            icon="🎮",
            enabled=True,
            visible=True,
            order=2,
            description="AI对战游戏（斗地主/麻将）",
        ),
        ModuleConfig(
            module_id="research",
            name="研究助手",
            icon="🔍",
            enabled=True,
            visible=True,
            order=3,
            description="AI增强搜索与研究",
            auto_refresh=False,
        ),
        ModuleConfig(
            module_id="writing",
            name="写作助手",
            icon="✍️",
            enabled=True,
            visible=True,
            order=4,
            description="AI写作与文档生成",
        ),
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else self._get_config_path()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._modules: dict[str, ModuleConfig] = {}
        self._states: dict[str, ModuleState] = {}
        
        self._load()
    
    def _get_config_path(self) -> Path:
        """获取配置路径"""
        return Path.home() / ".hermes-desktop" / "modules_config.json"
    
    def _load(self):
        """加载配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                # 加载模块配置
                for mod in data.get("modules", []):
                    cfg = ModuleConfig(**mod)
                    self._modules[cfg.module_id] = cfg
                
                # 加载模块状态
                for state in data.get("states", []):
                    s = ModuleState(**state)
                    self._states[s.module_id] = s
                
                return
            except (json.JSONDecodeError, KeyError):
                pass
        
        # 使用默认配置
        for mod in self.DEFAULT_MODULES:
            self._modules[mod.module_id] = mod
            self._states[mod.module_id] = ModuleState(module_id=mod.module_id)
    
    def save(self):
        """保存配置"""
        data = {
            "modules": [m.__dict__ for m in self._modules.values()],
            "states": [s.__dict__ for s in self._states.values()],
        }
        
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_module(self, module_id: str) -> Optional[ModuleConfig]:
        """获取模块配置"""
        return self._modules.get(module_id)
    
    def get_all_modules(self) -> list[ModuleConfig]:
        """获取所有模块（按顺序）"""
        modules = list(self._modules.values())
        modules.sort(key=lambda x: x.order)
        return modules
    
    def get_visible_modules(self) -> list[ModuleConfig]:
        """获取可见模块"""
        return [m for m in self.get_all_modules() if m.visible and m.enabled]
    
    def is_visible(self, module_id: str) -> bool:
        """检查模块是否可见"""
        mod = self._modules.get(module_id)
        return mod.visible if mod else False
    
    def set_visible(self, module_id: str, visible: bool):
        """设置模块可见性"""
        mod = self._modules.get(module_id)
        if mod:
            mod.visible = visible
            self.save()
    
    def is_enabled(self, module_id: str) -> bool:
        """检查模块是否启用"""
        mod = self._modules.get(module_id)
        return mod.enabled if mod else False
    
    def set_enabled(self, module_id: str, enabled: bool):
        """设置模块启用状态"""
        mod = self._modules.get(module_id)
        if mod:
            mod.enabled = enabled
            self.save()
    
    def set_order(self, module_order: list[str]):
        """设置模块顺序"""
        for i, module_id in enumerate(module_order):
            mod = self._modules.get(module_id)
            if mod:
                mod.order = i
        self.save()
    
    def get_state(self, module_id: str) -> Optional[ModuleState]:
        """获取模块状态"""
        return self._states.get(module_id)
    
    def update_state(self, module_id: str, **kwargs):
        """更新模块状态"""
        if module_id not in self._states:
            self._states[module_id] = ModuleState(module_id=module_id)
        
        state = self._states[module_id]
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
    
    def reset_to_default(self):
        """重置为默认配置"""
        self._modules.clear()
        self._states.clear()
        
        for mod in self.DEFAULT_MODULES:
            self._modules[mod.module_id] = mod
            self._states[mod.module_id] = ModuleState(module_id=mod.module_id)
        
        self.save()
    
    def get_config_json(self) -> str:
        """导出配置为JSON"""
        return json.dumps({
            "modules": [m.__dict__ for m in self._modules.values()],
        }, ensure_ascii=False, indent=2)
    
    def import_config(self, json_str: str):
        """从JSON导入配置"""
        try:
            data = json.loads(json_str)
            for mod in data.get("modules", []):
                cfg = ModuleConfig(**mod)
                self._modules[cfg.module_id] = cfg
            self.save()
            return True
        except (json.JSONDecodeError, KeyError, TypeError):
            return False


# 全局单例
_module_manager: Optional[ModuleManager] = None


def get_module_manager() -> ModuleManager:
    """获取全局模块管理器"""
    global _module_manager
    if _module_manager is None:
        _module_manager = ModuleManager()
    return _module_manager
