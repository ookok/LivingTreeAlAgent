"""
用户脚本系统

借鉴 qutebrowser 的用户脚本系统，为 AI 增强浏览器提供用户脚本功能
"""

import os
import subprocess
import tempfile
from typing import Dict, List, Optional
from dataclasses import dataclass

from ..browser_pool import BrowserSession


@dataclass
class UserScript:
    """用户脚本信息"""
    name: str
    path: str
    enabled: bool = True
    description: str = ""
    author: str = ""
    version: str = "1.0.0"


class UserScriptManager:
    """用户脚本管理器"""
    
    def __init__(self):
        self._scripts: Dict[str, UserScript] = {}
        self._script_paths: List[str] = []
        self._session: Optional[BrowserSession] = None
    
    def add_script_path(self, path: str):
        """
        添加脚本路径
        
        Args:
            path: 脚本路径
        """
        if path not in self._script_paths:
            self._script_paths.append(path)
    
    def load_scripts(self, session: BrowserSession):
        """
        加载所有脚本
        
        Args:
            session: 浏览器会话
        """
        self._session = session
        
        for path in self._script_paths:
            if os.path.isdir(path):
                self._load_scripts_from_dir(path)
    
    def _load_scripts_from_dir(self, dir_path: str):
        """
        从目录加载脚本
        
        Args:
            dir_path: 目录路径
        """
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            if os.path.isfile(item_path) and self._is_valid_script(item_path):
                self._load_script(item_path)
    
    def _is_valid_script(self, script_path: str) -> bool:
        """
        检查是否为有效的脚本文件
        
        Args:
            script_path: 脚本路径
            
        Returns:
            bool: 是否为有效脚本
        """
        # 检查文件是否可执行
        if os.access(script_path, os.X_OK):
            return True
        
        # 检查文件扩展名
        ext = os.path.splitext(script_path)[1].lower()
        valid_extensions = ['.py', '.js', '.sh', '.bat', '.cmd']
        return ext in valid_extensions
    
    def _load_script(self, script_path: str):
        """
        加载单个脚本
        
        Args:
            script_path: 脚本路径
        """
        try:
            # 提取脚本信息
            script_name = os.path.basename(script_path)
            script = UserScript(
                name=script_name,
                path=script_path
            )
            
            # 尝试从脚本文件中提取元数据
            self._extract_script_metadata(script)
            
            self._scripts[script.name] = script
            print(f"Loaded user script: {script.name}")
            
        except Exception as e:
            print(f"Failed to load script from {script_path}: {e}")
    
    def _extract_script_metadata(self, script: UserScript):
        """
        从脚本文件中提取元数据
        
        Args:
            script: 脚本实例
        """
        try:
            with open(script.path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 尝试提取元数据（基于注释）
            import re
            
            # 提取描述
            desc_match = re.search(r'#.*@description\s+(.*)', content)
            if desc_match:
                script.description = desc_match.group(1).strip()
            
            # 提取作者
            author_match = re.search(r'#.*@author\s+(.*)', content)
            if author_match:
                script.author = author_match.group(1).strip()
            
            # 提取版本
            version_match = re.search(r'#.*@version\s+(.*)', content)
            if version_match:
                script.version = version_match.group(1).strip()
                
        except Exception:
            pass
    
    def run_script(self, script_name: str, *args, **kwargs) -> Optional[Dict]:
        """
        运行脚本
        
        Args:
            script_name: 脚本名称
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            Dict: 脚本执行结果
        """
        if script_name not in self._scripts or not self._scripts[script_name].enabled:
            return None
        
        script = self._scripts[script_name]
        
        try:
            # 构建环境变量
            env = os.environ.copy()
            
            # 添加浏览器会话信息
            if self._session:
                env['BROWSER_SESSION_ID'] = self._session.session_id
                env['BROWSER_URL'] = self._session.browser.current_url if hasattr(self._session.browser, 'current_url') else ''
            
            # 添加脚本参数
            script_args = list(args)
            
            # 处理关键字参数
            for key, value in kwargs.items():
                script_args.append(f'--{key}={value}')
            
            # 执行脚本
            result = subprocess.run(
                [script.path] + script_args,
                env=env,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def run_script_on_page(self, script_name: str, url: str) -> Optional[Dict]:
        """
        在指定页面上运行脚本
        
        Args:
            script_name: 脚本名称
            url: 页面 URL
            
        Returns:
            Dict: 脚本执行结果
        """
        return self.run_script(script_name, url)
    
    def get_script(self, name: str) -> Optional[UserScript]:
        """
        获取脚本
        
        Args:
            name: 脚本名称
            
        Returns:
            UserScript: 脚本实例
        """
        return self._scripts.get(name)
    
    def list_scripts(self) -> List[UserScript]:
        """
        列出所有脚本
        
        Returns:
            List[UserScript]: 脚本列表
        """
        return list(self._scripts.values())
    
    def enable_script(self, name: str):
        """
        启用脚本
        
        Args:
            name: 脚本名称
        """
        if name in self._scripts:
            self._scripts[name].enabled = True
    
    def disable_script(self, name: str):
        """
        禁用脚本
        
        Args:
            name: 脚本名称
        """
        if name in self._scripts:
            self._scripts[name].enabled = False
    
    def unload_scripts(self):
        """
        卸载所有脚本
        """
        self._scripts.clear()
        self._session = None


# 单例实例
_user_script_manager: Optional[UserScriptManager] = None


def get_user_script_manager() -> UserScriptManager:
    """
    获取用户脚本管理器实例
    
    Returns:
        UserScriptManager: 用户脚本管理器实例
    """
    global _user_script_manager
    if _user_script_manager is None:
        _user_script_manager = UserScriptManager()
    return _user_script_manager
