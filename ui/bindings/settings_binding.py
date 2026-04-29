# -*- coding: utf-8 -*-
"""
Settings Binding - 设置面板与业务逻辑绑定

将 PyDracula UI 设置组件与 Config/SmartConfig 连接
支持用户设置和系统设置
"""

from typing import Optional, Dict, Any, Callable
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QWidget, QComboBox, QLineEdit, QCheckBox, QSpinBox,
    QSlider, QLabel, QGroupBox, QFormLayout, QVBoxLayout
)


class SettingsBinding(QObject):
    """
    设置面板业务逻辑绑定

    Signals:
        setting_changed: 设置项变更
        config_saved: 配置已保存
        config_loaded: 配置已加载
        validation_error: 验证错误
    """

    setting_changed = Signal(str, object)  # (key, value)
    config_saved = Signal(dict)
    config_loaded = Signal(dict)
    validation_error = Signal(str, str)  # (key, error_message)

    # 设置分类
    CATEGORY_USER = "user"
    CATEGORY_SYSTEM = "system"

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._parent = parent
        self._config = None
        self._smart_config = None
        self._initialized = False

        # 设置项映射
        self._user_settings_widgets: Dict[str, QWidget] = {}
        self._system_settings_widgets: Dict[str, QWidget] = {}

        # 默认值
        self._default_config: Dict[str, Any] = {}

    def initialize(self, category: str = None):
        """
        初始化设置绑定

        Args:
            category: 初始化类别 (user/system/None=全部)
        """
        if self._initialized and category is None:
            return

        try:
            # 加载配置
            from client.src.business.config import load_config, AppConfig
            self._config = load_config()

            # 尝试加载 SmartConfig
            try:
                from client.src.business.smart_config import SmartConfig
                self._smart_config = SmartConfig()
            except ImportError:
                print("[SettingsBinding] SmartConfig not available")
                self._smart_config = None

            # 根据类别初始化
            if category in (None, self.CATEGORY_USER):
                self._init_user_settings()

            if category in (None, self.CATEGORY_SYSTEM):
                self._init_system_settings()

            self._initialized = True
            self.config_loaded.emit(self._get_config_dict())

        except Exception as e:
            print(f"[SettingsBinding] Initialize error: {e}")
            self.validation_error.emit("global", f"配置加载失败: {e}")

    def _init_user_settings(self):
        """初始化用户设置"""
        # 用户设置项
        self._user_settings = {
            # 外观
            'theme': {
                'type': 'combobox',
                'label': '界面主题',
                'options': [('light', '亮色'), ('dark', '深色'), ('auto', '跟随系统')],
                'default': 'dark',
            },
            'language': {
                'type': 'combobox',
                'label': '界面语言',
                'options': [('zh', '中文'), ('en', 'English')],
                'default': 'zh',
            },
            'font_size': {
                'type': 'spinbox',
                'label': '字体大小',
                'min': 10,
                'max': 24,
                'default': 14,
            },

            # 聊天
            'chat_auto_save': {
                'type': 'checkbox',
                'label': '自动保存聊天记录',
                'default': True,
            },
            'chat_show_timestamps': {
                'type': 'checkbox',
                'label': '显示消息时间戳',
                'default': True,
            },
            'chat_max_history': {
                'type': 'spinbox',
                'label': '最大历史消息数',
                'min': 100,
                'max': 10000,
                'default': 1000,
            },

            # 通知
            'notifications_enabled': {
                'type': 'checkbox',
                'label': '启用通知',
                'default': True,
            },
            'notification_sound': {
                'type': 'checkbox',
                'label': '通知声音',
                'default': True,
            },
        }

    def _init_system_settings(self):
        """初始化系统设置"""
        # 系统设置项
        self._system_settings = {
            # Ollama 配置
            'ollama_base_url': {
                'type': 'lineedit',
                'label': 'Ollama 服务器地址',
                'default': 'http://localhost:11434',
            },
            'ollama_default_model': {
                'type': 'lineedit',
                'label': '默认模型',
                'default': '',
            },
            'ollama_keep_alive': {
                'type': 'spinbox',
                'label': '模型保持时间 (分钟)',
                'min': 1,
                'max': 60,
                'default': 5,
            },

            # Agent 配置
            'agent_max_iterations': {
                'type': 'spinbox',
                'label': '最大迭代次数',
                'min': 1,
                'max': 200,
                'default': 90,
            },
            'agent_temperature': {
                'type': 'slider',
                'label': '温度参数',
                'min': 0,
                'max': 100,  # 百分比
                'default': 70,
            },
            'agent_streaming': {
                'type': 'checkbox',
                'label': '启用流式输出',
                'default': True,
            },

            # 搜索配置
            'search_cache_ttl': {
                'type': 'spinbox',
                'label': '搜索缓存有效期 (分钟)',
                'min': 10,
                'max': 1440,
                'default': 60,
            },

            # 存储配置
            'storage_models_dir': {
                'type': 'lineedit',
                'label': '模型存储目录',
                'default': '',
            },
        }

    def bind_widget(self, key: str, widget: QWidget, category: str = CATEGORY_USER):
        """
        绑定设置组件

        Args:
            key: 设置项键名
            widget: Qt 组件
            category: 设置类别 (user/system)
        """
        if category == self.CATEGORY_USER:
            self._user_settings_widgets[key] = widget
        else:
            self._system_settings_widgets[key] = widget

        # 连接信号
        self._connect_widget_signal(key, widget, category)

        # 加载当前值
        self._load_widget_value(key, widget, category)

    def _connect_widget_signal(self, key: str, widget: QWidget, category: str):
        """连接组件信号"""
        if isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(
                lambda idx: self._on_setting_changed(key, widget.currentData(), category)
            )
        elif isinstance(widget, QCheckBox):
            widget.toggled.connect(
                lambda checked: self._on_setting_changed(key, checked, category)
            )
        elif isinstance(widget, (QSpinBox, QSlider)):
            widget.valueChanged.connect(
                lambda val: self._on_setting_changed(key, val, category)
            )
        elif isinstance(widget, QLineEdit):
            widget.editingFinished.connect(
                lambda: self._on_setting_changed(key, widget.text(), category)
            )

    def _load_widget_value(self, key: str, widget: QWidget, category: str):
        """加载组件当前值"""
        value = self._get_setting_value(key, category)

        if isinstance(widget, QComboBox):
            # 根据数据找到匹配的索引
            for i in range(widget.count()):
                if widget.itemData(i) == value:
                    widget.setCurrentIndex(i)
                    break
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value))
        elif isinstance(widget, QSlider):
            widget.setValue(int(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))

    def _on_setting_changed(self, key: str, value: Any, category: str):
        """设置项变更处理"""
        # 验证
        if not self._validate_setting(key, value, category):
            return

        # 保存
        self._set_setting_value(key, value, category)

        # 发送信号
        self.setting_changed.emit(key, value)

    def _validate_setting(self, key: str, value: Any, category: str) -> bool:
        """验证设置值"""
        settings = self._get_settings_dict(category)
        if not settings or key not in settings:
            return True  # 未知设置项，直接通过

        spec = settings[key]
        spec_type = spec.get('type')

        if spec_type == 'lineedit':
            if key == 'ollama_base_url':
                if value and not value.startswith(('http://', 'https://')):
                    self.validation_error.emit(key, 'URL 必须以 http:// 或 https:// 开头')
                    return False

        return True

    def _get_setting_value(self, key: str, category: str) -> Any:
        """获取设置值"""
        if category == self.CATEGORY_USER:
            settings = self._user_settings
        else:
            settings = self._system_settings

        if key in settings:
            default = settings[key].get('default', '')
            # 从配置中获取
            if self._config:
                return getattr(self._config, key, default)
            return default

        # 尝试从 _config 获取
        if self._config and hasattr(self._config, key):
            return getattr(self._config, key)

        return None

    def _set_setting_value(self, key: str, value: Any, category: str):
        """设置值"""
        settings = self._get_settings_dict(category)
        if settings and key in settings:
            settings[key]['_current_value'] = value

        # 如果是主题设置，立即应用
        if key == 'theme':
            self._apply_theme(value)

    def _apply_theme(self, theme: str):
        """应用主题"""
        try:
            from ui.theme_manager import get_theme_manager
            tm = get_theme_manager()
            if theme == 'light':
                tm.set_theme(is_light=True)
            elif theme == 'dark':
                tm.set_theme(is_light=False)
            # 'auto' 暂时使用系统默认
        except Exception as e:
            print(f"[SettingsBinding] Apply theme error: {e}")

    def _get_settings_dict(self, category: str) -> Dict:
        """获取设置字典"""
        if category == self.CATEGORY_USER:
            return self._user_settings
        return self._system_settings

    def _get_config_dict(self) -> Dict[str, Any]:
        """获取配置字典"""
        if self._config:
            return self._config.model_dump()
        return {}

    def get_all_user_settings(self) -> Dict[str, Any]:
        """获取所有用户设置"""
        result = {}
        for key, spec in self._user_settings.items():
            result[key] = self._get_setting_value(key, self.CATEGORY_USER)
        return result

    def get_all_system_settings(self) -> Dict[str, Any]:
        """获取所有系统设置"""
        result = {}
        for key, spec in self._system_settings.items():
            result[key] = self._get_setting_value(key, self.CATEGORY_SYSTEM)
        return result

    def save_config(self):
        """保存配置"""
        if not self._config:
            return

        try:
            # 更新配置对象
            for key, spec in self._user_settings.items():
                if '_current_value' in spec:
                    self._set_config_attr(key, spec['_current_value'])

            for key, spec in self._system_settings.items():
                if '_current_value' in spec:
                    self._set_config_attr(key, spec['_current_value'])

            # 保存到文件
            from client.src.business.config import save_config
            save_config(self._config)

            self.config_saved.emit(self._get_config_dict())

        except Exception as e:
            self.validation_error.emit("global", f"保存失败: {e}")

    def _set_config_attr(self, key: str, value: Any):
        """设置配置属性"""
        if self._config and hasattr(self._config, key):
            try:
                setattr(self._config, key, value)
            except Exception as e:
                print(f"[SettingsBinding] Set attr error: {e}")

    def reset_to_defaults(self, category: str = None):
        """
        重置为默认值

        Args:
            category: 重置类别 (user/system/None=全部)
        """
        if category in (None, self.CATEGORY_USER):
            for key, spec in self._user_settings.items():
                default = spec.get('default')
                self._load_widget_value(key, self._user_settings_widgets.get(key), self.CATEGORY_USER)

        if category in (None, self.CATEGORY_SYSTEM):
            for key, spec in self._system_settings.items():
                self._load_widget_value(key, self._system_settings_widgets.get(key), self.CATEGORY_SYSTEM)

    def create_settings_ui(self, category: str = CATEGORY_USER, parent: QWidget = None) -> QWidget:
        """
        创建设置 UI

        Args:
            category: 设置类别
            parent: 父组件

        Returns:
            包含所有设置项的 widget
        """
        container = QWidget(parent)
        layout = QVBoxLayout(container)

        settings = self._get_settings_dict(category)

        for key, spec in settings.items():
            group = QGroupBox(spec.get('label', key), container)
            group_layout = QFormLayout(group)

            widget = self._create_setting_widget(key, spec)
            if widget:
                group_layout.addRow(widget)
                self.bind_widget(key, widget, category)

            layout.addWidget(group)

        layout.addStretch()
        return container

    def _create_setting_widget(self, key: str, spec: Dict) -> QWidget:
        """创建设置组件"""
        widget_type = spec.get('type', 'lineedit')

        if widget_type == 'combobox':
            widget = QComboBox()
            for data, text in spec.get('options', []):
                widget.addItem(text, data)
        elif widget_type == 'checkbox':
            widget = QCheckBox()
        elif widget_type == 'spinbox':
            widget = QSpinBox()
            widget.setRange(spec.get('min', 0), spec.get('max', 100))
        elif widget_type == 'slider':
            widget = QSlider()
            widget.setRange(spec.get('min', 0), spec.get('max', 100))
            widget.setOrientation(Qt.Horizontal)
        else:
            widget = QLineEdit()

        return widget

    def cleanup(self):
        """清理资源"""
        self._initialized = False
        self._config = None
        self._smart_config = None


# Qt import for widget types
try:
    from PySide6.QtCore import Qt
except ImportError:
    from PyQt6.QtCore import Qt
