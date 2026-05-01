"""
主题系统 - Theme System

功能：
1. 主题切换
2. CSS变量管理
3. 热更新支持
4. 主题持久化
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ThemeType(Enum):
    """主题类型"""
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class ThemeSystem:
    """
    主题系统 - 管理应用主题
    
    核心功能：
    1. 内置主题支持
    2. 自定义主题
    3. CSS变量注入
    4. 热更新
    """
    
    def __init__(self):
        self._current_theme = ThemeType.DARK
        self._themes: Dict[str, Dict[str, str]] = {}
        self._theme_path = os.path.join(os.path.expanduser("~"), ".hermes", "themes")
        
        # 加载内置主题
        self._load_builtin_themes()
        
        # 加载自定义主题
        self._load_custom_themes()
    
    def _load_builtin_themes(self):
        """加载内置主题"""
        self._themes['light'] = {
            '--bg-primary': '#ffffff',
            '--bg-secondary': '#f5f5f5',
            '--bg-tertiary': '#e8e8e8',
            '--text-primary': '#1a1a1a',
            '--text-secondary': '#666666',
            '--text-muted': '#999999',
            '--accent-primary': '#007acc',
            '--accent-secondary': '#00d4ff',
            '--border-color': '#e0e0e0',
            '--success': '#00ff88',
            '--warning': '#ffa502',
            '--error': '#ff4757',
            '--shadow': 'rgba(0, 0, 0, 0.1)'
        }
        
        self._themes['dark'] = {
            '--bg-primary': '#1a1a2e',
            '--bg-secondary': '#16213e',
            '--bg-tertiary': '#0f3460',
            '--text-primary': '#ffffff',
            '--text-secondary': 'rgba(255, 255, 255, 0.8)',
            '--text-muted': 'rgba(255, 255, 255, 0.5)',
            '--accent-primary': '#00d4ff',
            '--accent-secondary': '#7b2fff',
            '--border-color': 'rgba(255, 255, 255, 0.1)',
            '--success': '#00ff88',
            '--warning': '#ffa502',
            '--error': '#ff4757',
            '--shadow': 'rgba(0, 0, 0, 0.3)'
        }
        
        self._themes['system'] = self._themes['dark']  # 默认使用深色
    
    def _load_custom_themes(self):
        """加载自定义主题"""
        os.makedirs(self._theme_path, exist_ok=True)
        
        for filename in os.listdir(self._theme_path):
            if filename.endswith('.json'):
                theme_id = filename[:-5]
                filepath = os.path.join(self._theme_path, filename)
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        theme_data = json.load(f)
                        self._themes[theme_id] = theme_data
                        logger.info(f"加载自定义主题: {theme_id}")
                except Exception as e:
                    logger.error(f"加载主题失败 {filename}: {e}")
    
    def set_theme(self, theme_type: ThemeType):
        """设置主题"""
        self._current_theme = theme_type
        self._apply_theme()
        self._save_preference()
    
    def _apply_theme(self):
        """应用主题到全局样式"""
        theme = self._themes.get(self._current_theme.value)
        
        if theme:
            # 生成CSS变量字符串
            css_vars = '\n'.join([f'{key}: {value};' for key, value in theme.items()])
            
            # 通过WebEngine注入CSS
            self._inject_css(css_vars)
    
    def _inject_css(self, css_vars: str):
        """注入CSS变量到页面"""
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        
        # 这里需要获取全局WebView实例
        # 实际实现时需要通过依赖注入或全局引用
        pass
    
    def _save_preference(self):
        """保存主题偏好设置"""
        pref_path = os.path.join(os.path.expanduser("~"), ".hermes", "preferences.json")
        
        try:
            os.makedirs(os.path.dirname(pref_path), exist_ok=True)
            
            preferences = {}
            if os.path.exists(pref_path):
                with open(pref_path, 'r') as f:
                    preferences = json.load(f)
            
            preferences['theme'] = self._current_theme.value
            
            with open(pref_path, 'w') as f:
                json.dump(preferences, f, indent=2)
        except Exception as e:
            logger.error(f"保存主题偏好失败: {e}")
    
    def load_preference(self):
        """加载主题偏好设置"""
        pref_path = os.path.join(os.path.expanduser("~"), ".hermes", "preferences.json")
        
        if os.path.exists(pref_path):
            try:
                with open(pref_path, 'r') as f:
                    preferences = json.load(f)
                    theme_value = preferences.get('theme', 'dark')
                    self._current_theme = ThemeType(theme_value)
            except Exception as e:
                logger.error(f"加载主题偏好失败: {e}")
    
    def get_current_theme(self) -> ThemeType:
        """获取当前主题"""
        return self._current_theme
    
    def get_theme_variables(self) -> Dict[str, str]:
        """获取主题变量"""
        return self._themes.get(self._current_theme.value, {})
    
    def get_available_themes(self) -> List[str]:
        """获取可用主题列表"""
        return list(self._themes.keys())
    
    def create_theme(self, theme_id: str, variables: Dict[str, str]):
        """创建自定义主题"""
        self._themes[theme_id] = variables
        
        # 保存到文件
        filepath = os.path.join(self._theme_path, f"{theme_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(variables, f, indent=2)
        
        logger.info(f"创建自定义主题: {theme_id}")
    
    def remove_theme(self, theme_id: str):
        """删除自定义主题"""
        if theme_id in ['light', 'dark', 'system']:
            logger.warning("无法删除内置主题")
            return
        
        if theme_id in self._themes:
            del self._themes[theme_id]
            
            filepath = os.path.join(self._theme_path, f"{theme_id}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
            
            logger.info(f"删除主题: {theme_id}")