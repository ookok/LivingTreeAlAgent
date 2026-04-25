"""
browser-use 适配器

将 browser-use 集成到本项目的浏览器网关系统中
"""

import asyncio
import os
from typing import Optional, Dict, Any, List

from browser_use import Agent, Browser
from browser_use import ChatOpenAI, ChatAnthropic, ChatGoogle

from ..standalone import StandaloneRuntime
from .browser_pool import get_browser_pool, BrowserSession
from .security_manager import get_security_manager
from .extensions import get_extension_manager, get_plugin_system, get_user_script_manager
from .config import get_config_manager, ConfigOption, ConfigType
from .config.config_validator import RangeValidator, ChoicesValidator


def _get_api_key(provider: str) -> Optional[str]:
    """获取 API Key（兼容统一配置）"""
    try:
        from core.config.unified_config import get_config
        key = get_config().get_api_key(provider)
        if key:
            return key
    except Exception:
        pass
    # 回退到环境变量
    env_var = f"{provider.upper()}_API_KEY"
    return os.getenv(env_var)


class BrowserUseAdapter:
    """browser-use 适配器"""
    
    def __init__(self, runtime: Optional[StandaloneRuntime] = None):
        """
        初始化 browser-use 适配器
        
        Args:
            runtime: 独立运行时实例
        """
        self.runtime = runtime
        self.agent: Optional[Agent] = None
        self._initialized = False
        self._current_session: Optional[BrowserSession] = None
        self._browser_pool = get_browser_pool()
        self._security_manager = get_security_manager()
        self._extension_manager = get_extension_manager()
        self._plugin_system = get_plugin_system()
        self._user_script_manager = get_user_script_manager()
        self._config_manager = get_config_manager()
        self._init_config()
    
    def _init_config(self):
        """
        初始化配置
        """
        # 添加配置选项
        options = [
            ConfigOption(
                name="browser.timeout",
                default=30,
                config_type=ConfigType.INT,
                description="浏览器操作超时时间（秒）",
                validator=RangeValidator(min_value=1, max_value=300)
            ),
            ConfigOption(
                name="browser.max_retries",
                default=3,
                config_type=ConfigType.INT,
                description="浏览器操作最大重试次数",
                validator=RangeValidator(min_value=0, max_value=10)
            ),
            ConfigOption(
                name="browser.user_agent",
                default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                config_type=ConfigType.STRING,
                description="浏览器用户代理"
            ),
            ConfigOption(
                name="extensions.enabled",
                default=True,
                config_type=ConfigType.BOOL,
                description="是否启用扩展"
            ),
            ConfigOption(
                name="plugins.enabled",
                default=True,
                config_type=ConfigType.BOOL,
                description="是否启用插件"
            ),
            ConfigOption(
                name="user_scripts.enabled",
                default=True,
                config_type=ConfigType.BOOL,
                description="是否启用用户脚本"
            )
        ]
        self._config_manager.add_options(options)
        
        # 设置配置文件路径
        import os
        config_dir = os.path.join(os.path.expanduser("~"), ".livingtree", "config")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "browser_config.json")
        self._config_manager.set_config_path(config_path)
        
        # 加载配置
        self._config_manager.load()
    
    async def initialize(self, use_cloud: bool = False) -> bool:
        """
        初始化 browser-use
        
        Args:
            use_cloud: 是否使用云浏览器
            
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 初始化代理（浏览器会话将在执行任务时从池获取）
            self.agent = Agent(
                task="",  # 任务将在每次执行时设置
                llm=self._get_llm(),
                browser=None,  # 浏览器将在执行时设置
                max_steps=50
            )
            
            self._initialized = True
            return True
            
        except Exception as e:
            print(f"初始化 browser-use 失败: {e}")
            return False
    
    def _get_llm(self):
        """
        获取 LLM 实例
        
        Returns:
            LLM 实例
        """
        # 优先使用 ChatBrowserUse
        try:
            from browser_use import ChatBrowserUse
            return ChatBrowserUse()
        except ImportError:
            # 回退到 OpenAI（通过统一配置）
            try:
                api_key = _get_api_key("openai")
                if api_key:
                    return ChatOpenAI(model="gpt-4o", api_key=api_key)
            except Exception:
                pass
        
        # 回退到 Google
        try:
            api_key = _get_api_key("google")
            if api_key:
                return ChatGoogle(model="gemini-3-flash-preview", api_key=api_key)
        except Exception:
            pass
        
        # 回退到 Anthropic
        try:
            api_key = _get_api_key("anthropic")
            if api_key:
                return ChatAnthropic(model="claude-sonnet-4-6", api_key=api_key)
        except Exception:
            pass
        
        # 最后回退到默认的 ChatBrowserUse
        from browser_use import ChatBrowserUse
        return ChatBrowserUse()
    
    async def execute_task(self, task: str) -> Dict[str, Any]:
        """
        执行浏览器任务
        
        Args:
            task: 任务描述
            
        Returns:
            Dict: 执行结果
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 提取并检查 URL
            urls = self._extract_urls_from_task(task)
            for url in urls:
                if not self._security_manager.is_allowed(url, "navigate"):
                    return {
                        "success": False,
                        "error": f"访问被拒绝：{url} 不在允许的域名列表中",
                        "task": task
                    }
            
            # 从会话池获取浏览器会话
            session = await self._browser_pool.get_session()
            self._current_session = session
            
            # 加载扩展、插件和用户脚本
            self._load_extensions(session)
            
            # 设置代理的浏览器
            self.agent.browser = session.browser
            
            # 更新任务
            self.agent.task = task
            
            # 执行任务
            result = await self.agent.run()
            
            # 提取结果
            output = {
                "success": True,
                "task": task,
                "final_result": result.final_result(),
                "is_successful": result.is_successful(),
                "steps": len(result.history),
                "session_id": session.session_id
            }
            
            # 释放会话
            await self._browser_pool.release_session(session.session_id)
            self._current_session = None
            
            return output
            
        except Exception as e:
            # 释放会话
            if self._current_session:
                try:
                    await self._browser_pool.release_session(self._current_session.session_id)
                except:
                    pass
                self._current_session = None
            
            return {
                "success": False,
                "error": str(e),
                "task": task
            }
    
    def _load_extensions(self, session: BrowserSession):
        """
        加载扩展、插件和用户脚本
        
        Args:
            session: 浏览器会话
        """
        import os
        
        # 检查是否启用扩展
        if self._config_manager.get("extensions.enabled", True):
            # 添加扩展路径
            extension_dirs = [
                os.path.join(os.path.expanduser("~"), ".livingtree", "extensions"),
                os.path.join(os.path.dirname(__file__), "extensions", "default")
            ]
            
            for ext_dir in extension_dirs:
                if os.path.exists(ext_dir):
                    self._extension_manager.add_extension_path(ext_dir)
            
            # 加载扩展
            self._extension_manager.load_extensions(session)
        
        # 检查是否启用插件
        if self._config_manager.get("plugins.enabled", True):
            # 添加插件路径
            plugin_dirs = [
                os.path.join(os.path.expanduser("~"), ".livingtree", "plugins"),
                os.path.join(os.path.dirname(__file__), "extensions", "plugins")
            ]
            
            for plugin_dir in plugin_dirs:
                if os.path.exists(plugin_dir):
                    self._plugin_system.add_plugin_path(plugin_dir)
            
            # 加载插件
            self._plugin_system.load_plugins()
        
        # 检查是否启用用户脚本
        if self._config_manager.get("user_scripts.enabled", True):
            # 添加用户脚本路径
            script_dirs = [
                os.path.join(os.path.expanduser("~"), ".livingtree", "user_scripts"),
                os.path.join(os.path.dirname(__file__), "extensions", "user_scripts")
            ]
            
            for script_dir in script_dirs:
                if os.path.exists(script_dir):
                    self._user_script_manager.add_script_path(script_dir)
            
            # 加载用户脚本
            self._user_script_manager.load_scripts(session)
    
    def _extract_urls_from_task(self, task: str) -> List[str]:
        """
        从任务描述中提取 URL
        
        Args:
            task: 任务描述
            
        Returns:
            List[str]: 提取的 URL 列表
        """
        import re
        # 简单的 URL 正则表达式
        url_pattern = r'https?://[\w\-._~:/?#[\]@!$&\'()*+,;=.]+'
        return re.findall(url_pattern, task)
    
    async def navigate(self, url: str) -> Dict[str, Any]:
        """
        导航到指定 URL
        
        Args:
            url: 目标 URL
            
        Returns:
            Dict: 执行结果
        """
        task = f"导航到 {url}"
        return await self.execute_task(task)
    
    async def extract_content(self, url: str, selector: Optional[str] = None) -> Dict[str, Any]:
        """
        提取页面内容
        
        Args:
            url: 目标 URL
            selector: CSS 选择器（可选）
            
        Returns:
            Dict: 执行结果
        """
        if selector:
            task = f"导航到 {url} 并提取 {selector} 选择器的内容"
        else:
            task = f"导航到 {url} 并提取页面主要内容"
        
        return await self.execute_task(task)
    
    async def fill_form(self, url: str, form_data: Dict[str, str]) -> Dict[str, Any]:
        """
        填写表单
        
        Args:
            url: 目标 URL
            form_data: 表单数据
            
        Returns:
            Dict: 执行结果
        """
        form_str = "\n".join([f"{key}: {value}" for key, value in form_data.items()])
        task = f"导航到 {url} 并填写表单，数据如下：\n{form_str}"
        
        return await self.execute_task(task)
    
    async def search(self, query: str, engine: str = "google") -> Dict[str, Any]:
        """
        搜索内容
        
        Args:
            query: 搜索查询
            engine: 搜索引擎（默认 google）
            
        Returns:
            Dict: 执行结果
        """
        task = f"在 {engine} 上搜索 '{query}' 并返回前 5 个结果"
        return await self.execute_task(task)
    
    async def screenshot(self, url: str, path: str = "screenshot.png") -> Dict[str, Any]:
        """
        截图页面
        
        Args:
            url: 目标 URL
            path: 保存路径
            
        Returns:
            Dict: 执行结果
        """
        task = f"导航到 {url} 并截取整个页面的截图，保存为 {path}"
        return await self.execute_task(task)
    
    async def close(self):
        """
        关闭浏览器
        """
        # 释放当前会话
        if self._current_session:
            try:
                await self._browser_pool.release_session(self._current_session.session_id)
            except Exception:
                pass
            self._current_session = None
        
        # 卸载扩展、插件和用户脚本
        self._extension_manager.unload_extensions()
        self._plugin_system.unload_plugins()
        self._user_script_manager.unload_scripts()
        
        self._initialized = False
        self.agent = None
    
    def is_initialized(self) -> bool:
        """
        检查是否初始化
        
        Returns:
            bool: 是否已初始化
        """
        return self._initialized


def create_browser_use_adapter(runtime: Optional[StandaloneRuntime] = None) -> BrowserUseAdapter:
    """
    创建 browser-use 适配器
    
    Args:
        runtime: 独立运行时实例
        
    Returns:
        BrowserUseAdapter: 适配器实例
    """
    return BrowserUseAdapter(runtime=runtime)
