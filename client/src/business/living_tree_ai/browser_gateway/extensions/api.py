"""
扩展 API

为扩展提供访问浏览器功能的接口
"""

from typing import Dict, Any, Optional, List
from ..browser_pool import BrowserSession
from .extension_manager import Extension


class ExtensionAPI:
    """扩展 API"""
    
    def __init__(self, session: BrowserSession, extension: Extension):
        """
        初始化扩展 API
        
        Args:
            session: 浏览器会话
            extension: 扩展实例
        """
        self._session = session
        self._extension = extension
        self._browser = session.browser
    
    # 浏览器操作 API
    async def navigate(self, url: str) -> Dict[str, Any]:
        """
        导航到指定 URL
        
        Args:
            url: 目标 URL
            
        Returns:
            Dict: 执行结果
        """
        try:
            if hasattr(self._browser, 'navigate'):
                await self._browser.navigate(url)
                return {
                    'success': True,
                    'url': url
                }
            else:
                return {
                    'success': False,
                    'error': 'Browser does not support navigate method'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_current_url(self) -> str:
        """
        获取当前 URL
        
        Returns:
            str: 当前 URL
        """
        try:
            if hasattr(self._browser, 'current_url'):
                return self._browser.current_url
            elif hasattr(self._browser, 'get_current_url'):
                return await self._browser.get_current_url()
            else:
                return ''
        except Exception:
            return ''
    
    async def get_page_content(self) -> str:
        """
        获取页面内容
        
        Returns:
            str: 页面内容
        """
        try:
            if hasattr(self._browser, 'page_content'):
                return self._browser.page_content
            elif hasattr(self._browser, 'get_page_content'):
                return await self._browser.get_page_content()
            else:
                return ''
        except Exception:
            return ''
    
    async def execute_javascript(self, script: str) -> Any:
        """
        执行 JavaScript
        
        Args:
            script: JavaScript 代码
            
        Returns:
            Any: 执行结果
        """
        try:
            if hasattr(self._browser, 'execute_script'):
                return await self._browser.execute_script(script)
            elif hasattr(self._browser, 'evaluate'):
                return await self._browser.evaluate(script)
            else:
                return None
        except Exception as e:
            return {
                'error': str(e)
            }
    
    async def click_element(self, selector: str) -> Dict[str, Any]:
        """
        点击元素
        
        Args:
            selector: CSS 选择器
            
        Returns:
            Dict: 执行结果
        """
        try:
            script = f"document.querySelector('{selector}').click();"
            await self.execute_javascript(script)
            return {
                'success': True
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def fill_form(self, selector: str, value: str) -> Dict[str, Any]:
        """
        填写表单
        
        Args:
            selector: CSS 选择器
            value: 填写值
            
        Returns:
            Dict: 执行结果
        """
        try:
            script = f"document.querySelector('{selector}').value = '{value}';"
            await self.execute_javascript(script)
            return {
                'success': True
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    # 扩展管理 API
    def get_extension_info(self) -> Dict[str, Any]:
        """
        获取扩展信息
        
        Returns:
            Dict: 扩展信息
        """
        return {
            'name': self._extension.name,
            'version': self._extension.version,
            'author': self._extension.author,
            'description': self._extension.description,
            'path': self._extension.path,
            'enabled': self._extension.enabled
        }
    
    def set_storage(self, key: str, value: Any) -> bool:
        """
        设置存储
        
        Args:
            key: 键
            value: 值
            
        Returns:
            bool: 是否成功
        """
        try:
            import json
            storage_path = self._get_storage_path()
            
            # 读取现有数据
            data = {}
            if storage_path.exists():
                with open(storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            # 更新数据
            data[key] = value
            
            # 保存数据
            with open(storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception:
            return False
    
    def get_storage(self, key: str, default: Any = None) -> Any:
        """
        获取存储
        
        Args:
            key: 键
            default: 默认值
            
        Returns:
            Any: 存储值
        """
        try:
            import json
            storage_path = self._get_storage_path()
            
            if storage_path.exists():
                with open(storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get(key, default)
            
            return default
        except Exception:
            return default
    
    def _get_storage_path(self):
        """
        获取存储路径
        
        Returns:
            Path: 存储路径
        """
        from pathlib import Path
        storage_dir = Path(self._extension.path) / 'storage'
        storage_dir.mkdir(exist_ok=True)
        return storage_dir / 'data.json'
    
    # 通知 API
    def show_notification(self, title: str, message: str, icon: str = None) -> bool:
        """
        显示通知
        
        Args:
            title: 标题
            message: 消息
            icon: 图标
            
        Returns:
            bool: 是否成功
        """
        try:
            # 这里可以实现通知功能
            print(f"[Notification] {title}: {message}")
            return True
        except Exception:
            return False
    
    # 配置 API
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取配置
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        try:
            import json
            config_path = Path(self._extension.path) / 'config.json'
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get(key, default)
            
            return default
        except Exception:
            return default
    
    def set_config(self, key: str, value: Any) -> bool:
        """
        设置配置
        
        Args:
            key: 配置键
            value: 配置值
            
        Returns:
            bool: 是否成功
        """
        try:
            import json
            from pathlib import Path
            config_path = Path(self._extension.path) / 'config.json'
            
            # 读取现有配置
            config = {}
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            # 更新配置
            config[key] = value
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception:
            return False
