"""
Mobile Adapter - 移动端适配模块

核心功能：
1. 响应式布局 - 自动适配不同屏幕尺寸
2. 触摸优化 - 优化触摸交互体验
3. 离线支持 - 支持离线操作和数据同步
4. 性能优化 - 针对移动设备优化性能

设计理念：
- 一次开发，多端适配
- 自动检测设备类型
- 提供统一的适配接口
"""

import json
import platform
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """设备类型"""
    DESKTOP = "desktop"
    TABLET = "tablet"
    MOBILE = "mobile"


class ScreenSize(Enum):
    """屏幕尺寸"""
    SMALL = "small"      # < 640px
    MEDIUM = "medium"    # 640px - 1024px
    LARGE = "large"      # > 1024px


@dataclass
class DeviceInfo:
    """设备信息"""
    type: DeviceType
    screen_size: ScreenSize
    os: str
    browser: Optional[str] = None
    pixel_ratio: float = 1.0
    touch_support: bool = False


@dataclass
class MobileConfig:
    """移动端配置"""
    responsive: bool = True
    touch_optimized: bool = True
    offline_mode: bool = False
    data_saver: bool = False
    font_scale: float = 1.0


class MobileAdapter:
    """
    移动端适配器
    
    核心特性：
    1. 设备检测 - 自动识别设备类型和屏幕尺寸
    2. 响应式适配 - 提供响应式布局支持
    3. 触摸优化 - 优化触摸交互
    4. 离线支持 - 支持离线操作
    """
    
    def __init__(self):
        self._device_info = self._detect_device()
        self._config = MobileConfig()
        logger.info(f"✅ MobileAdapter 初始化完成 - 设备类型: {self._device_info.type.value}")
    
    def _detect_device(self) -> DeviceInfo:
        """检测设备类型"""
        # 获取系统信息
        os_name = platform.system()
        
        # 默认桌面设备
        device_type = DeviceType.DESKTOP
        screen_size = ScreenSize.LARGE
        touch_support = False
        
        # 简化的设备检测（实际应用中会更复杂）
        if os_name == "Windows":
            device_type = DeviceType.DESKTOP
            screen_size = ScreenSize.LARGE
        elif os_name == "Darwin":
            # macOS 可能是桌面或移动设备
            device_type = DeviceType.DESKTOP
            screen_size = ScreenSize.LARGE
        elif os_name == "Linux":
            device_type = DeviceType.DESKTOP
            screen_size = ScreenSize.LARGE
        elif os_name == "Android":
            device_type = DeviceType.MOBILE
            screen_size = ScreenSize.SMALL
            touch_support = True
        elif os_name == "iOS":
            # iOS 可能是 iPhone 或 iPad
            device_type = DeviceType.MOBILE
            screen_size = ScreenSize.SMALL
            touch_support = True
        
        return DeviceInfo(
            type=device_type,
            screen_size=screen_size,
            os=os_name,
            touch_support=touch_support
        )
    
    def get_device_info(self) -> DeviceInfo:
        """获取设备信息"""
        return self._device_info
    
    def is_mobile(self) -> bool:
        """是否为移动设备"""
        return self._device_info.type in [DeviceType.MOBILE, DeviceType.TABLET]
    
    def is_desktop(self) -> bool:
        """是否为桌面设备"""
        return self._device_info.type == DeviceType.DESKTOP
    
    def get_adapted_content(self, content: str, max_length: Optional[int] = None) -> str:
        """
        获取适配后的内容
        
        Args:
            content: 原始内容
            max_length: 移动端最大长度限制
        
        Returns:
            适配后的内容
        """
        if not self.is_mobile():
            return content
        
        # 移动端内容优化
        if max_length and len(content) > max_length:
            content = content[:max_length] + "..."
        
        return content
    
    def get_adapted_font_size(self, base_size: int) -> int:
        """
        获取适配后的字体大小
        
        Args:
            base_size: 基础字体大小
        
        Returns:
            适配后的字体大小
        """
        if self._device_info.screen_size == ScreenSize.SMALL:
            return max(10, base_size - 2)
        elif self._device_info.screen_size == ScreenSize.MEDIUM:
            return base_size
        else:
            return base_size + 2
    
    def get_adapted_layout(self, layout: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取适配后的布局
        
        Args:
            layout: 原始布局配置
        
        Returns:
            适配后的布局配置
        """
        if not self.is_mobile():
            return layout
        
        adapted = layout.copy()
        
        # 移动端布局优化
        if "columns" in adapted:
            adapted["columns"] = min(adapted["columns"], 1)
        
        if "spacing" in adapted:
            adapted["spacing"] = max(4, int(adapted["spacing"] * 0.7))
        
        if "font_size" in adapted:
            adapted["font_size"] = self.get_adapted_font_size(adapted["font_size"])
        
        return adapted
    
    def enable_offline_mode(self):
        """启用离线模式"""
        self._config.offline_mode = True
        logger.info("✅ 离线模式已启用")
    
    def disable_offline_mode(self):
        """禁用离线模式"""
        self._config.offline_mode = False
    
    def is_offline_mode_enabled(self) -> bool:
        """是否启用离线模式"""
        return self._config.offline_mode
    
    def save_for_offline(self, key: str, data: Any):
        """保存数据供离线使用"""
        if not self._config.offline_mode:
            return
        
        # 简化实现：保存到文件
        offline_data = self._load_offline_data()
        offline_data[key] = {
            "data": data,
            "saved_at": self._get_current_time()
        }
        
        self._save_offline_data(offline_data)
        logger.info(f"✅ 数据已保存离线: {key}")
    
    def load_from_offline(self, key: str) -> Optional[Any]:
        """从离线存储加载数据"""
        offline_data = self._load_offline_data()
        item = offline_data.get(key)
        if item:
            return item.get("data")
        return None
    
    def _load_offline_data(self) -> Dict[str, Any]:
        """加载离线数据"""
        try:
            with open(".offline_data.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_offline_data(self, data: Dict[str, Any]):
        """保存离线数据"""
        with open(".offline_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _get_current_time(self) -> str:
        """获取当前时间"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_config(self) -> MobileConfig:
        """获取配置"""
        return self._config
    
    def update_config(self, **kwargs):
        """更新配置"""
        if "responsive" in kwargs:
            self._config.responsive = kwargs["responsive"]
        if "touch_optimized" in kwargs:
            self._config.touch_optimized = kwargs["touch_optimized"]
        if "offline_mode" in kwargs:
            self._config.offline_mode = kwargs["offline_mode"]
        if "data_saver" in kwargs:
            self._config.data_saver = kwargs["data_saver"]
        if "font_scale" in kwargs:
            self._config.font_scale = kwargs["font_scale"]


# 全局单例
_global_mobile_adapter: Optional[MobileAdapter] = None


def get_mobile_adapter() -> MobileAdapter:
    """获取全局移动端适配器单例"""
    global _global_mobile_adapter
    if _global_mobile_adapter is None:
        _global_mobile_adapter = MobileAdapter()
    return _global_mobile_adapter


# 测试函数
def test_mobile_adapter():
    """测试移动端适配器"""
    print("🧪 测试移动端适配器")
    print("="*60)
    
    adapter = get_mobile_adapter()
    
    # 获取设备信息
    print("\n📱 设备信息:")
    info = adapter.get_device_info()
    print(f"   类型: {info.type.value}")
    print(f"   屏幕: {info.screen_size.value}")
    print(f"   系统: {info.os}")
    print(f"   触摸支持: {info.touch_support}")
    
    # 检查设备类型
    print("\n🔍 设备检测:")
    print(f"   是否移动端: {adapter.is_mobile()}")
    print(f"   是否桌面端: {adapter.is_desktop()}")
    
    # 测试内容适配
    print("\n📝 内容适配:")
    long_text = "这是一段非常长的文本，用于测试移动端内容适配功能。" * 5
    adapted = adapter.get_adapted_content(long_text, 50)
    print(f"   原长: {len(long_text)}")
    print(f"   适配后: {len(adapted)}")
    print(f"   内容: {adapted}")
    
    # 测试字体大小适配
    print("\n🔤 字体适配:")
    print(f"   基础大小 14px -> {adapter.get_adapted_font_size(14)}px")
    print(f"   基础大小 16px -> {adapter.get_adapted_font_size(16)}px")
    
    # 测试离线模式
    print("\n📴 离线模式:")
    adapter.enable_offline_mode()
    adapter.save_for_offline("test_key", {"data": "test_value"})
    loaded = adapter.load_from_offline("test_key")
    print(f"   离线数据加载: {loaded}")
    
    print("\n🎉 移动端适配器测试完成！")
    return True


if __name__ == "__main__":
    test_mobile_adapter()