"""
浏览器自动化引导 - Browser Automation Guide

功能：
1. 预加载网站 - 减少等待时间
2. 高亮目标元素 - 引导用户注意力
3. 步骤指导 - 提供清晰的指引
4. 完成检测 - 自动检测配置完成

使用示例：
    browser_guide = BrowserAutomationGuide()
    
    # 创建引导
    guide = browser_guide.create_website_guide(
        website="https://openweathermap.org/signup",
        goal="get_api_key"
    )
    
    # 在UI中显示
    show_in_browser(guide["preloaded_url"], guide["highlight_script"])
"""

import os
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class GoalType(Enum):
    """目标类型"""
    GET_API_KEY = "get_api_key"
    LOGIN = "login"
    DOWNLOAD_FILE = "download_file"
    FILL_FORM = "fill_form"
    COPY_TEXT = "copy_text"


@dataclass
class WebsiteGuide:
    """
    网站引导
    
    Attributes:
        url: 预加载URL
        highlight_script: 高亮脚本
        steps: 步骤列表
        completion_detector: 完成检测器
        alternative_methods: 替代方法
    """
    url: str
    highlight_script: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    completion_detector: Dict[str, Any] = field(default_factory=dict)
    alternative_methods: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "highlight_script": self.highlight_script,
            "steps": self.steps,
            "completion_detector": self.completion_detector,
            "alternative_methods": self.alternative_methods,
        }


class BrowserAutomationGuide:
    """
    浏览器自动化引导系统
    
    辅助用户在第三方网站上完成注册、获取Key等操作
    """
    
    _instance: Optional["BrowserAutomationGuide"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 网站引导模板
        self._website_guides: Dict[str, WebsiteGuide] = {}
        self._init_builtin_guides()
        
        self._initialized = True
        logger.info("BrowserAutomationGuide initialized")
    
    def _init_builtin_guides(self):
        """初始化内置网站引导"""
        
        # OpenWeatherMap 注册引导
        self._website_guides["openweather_signup"] = WebsiteGuide(
            url="https://openweathermap.org/signup",
            highlight_script="""
// 高亮注册表单
document.querySelector('.signup-form')?.style.setProperty('border', '3px solid #00ff00', 'important');
document.querySelector('input[name="email"]')?.style.setProperty('background', '#e8f5e9', 'important');

// 高亮按钮
document.querySelector('button[type="submit"]')?.style.setProperty('background', '#4CAF50', 'important');
""",
            steps=[
                {
                    "title": "输入邮箱地址",
                    "description": "在邮箱输入框中输入您的邮箱",
                    "selector": "input[name='email']",
                    "action": "focus",
                },
                {
                    "title": "输入密码",
                    "description": "设置一个安全的密码",
                    "selector": "input[name='password']",
                    "action": "focus",
                },
                {
                    "title": "确认密码",
                    "description": "再次输入密码确认",
                    "selector": "input[name='password_confirm']",
                    "action": "focus",
                },
                {
                    "title": "点击注册",
                    "description": "点击注册按钮完成账号创建",
                    "selector": "button[type='submit']",
                    "action": "click",
                },
            ],
            completion_detector={
                "type": "url_contains",
                "pattern": "/home",
                "alternative": {
                    "type": "element_visible",
                    "selector": ".alert-success",
                },
            },
        )
        
        # OpenWeatherMap API Keys 页面引导
        self._website_guides["openweather_api_keys"] = WebsiteGuide(
            url="https://home.openweathermap.org/api_keys",
            highlight_script="""
// 高亮API Keys列表
document.querySelector('.api-keys')?.style.setProperty('border', '2px solid #2196F3', 'important');

// 高亮第一个Key
const firstKey = document.querySelector('.api-key-value');
if (firstKey) {
    firstKey.style.setProperty('background', '#fff3e0', 'important');
    firstKey.style.setProperty('padding', '10px', 'important');
}
""",
            steps=[
                {
                    "title": "找到API Key",
                    "description": "在列表中找到您的API Key（默认名称为API Key）",
                    "selector": ".api-key-value",
                    "action": "highlight",
                },
                {
                    "title": "复制Key",
                    "description": "点击复制按钮或手动复制Key的值",
                    "selector": ".copy-btn",
                    "action": "click",
                },
            ],
            completion_detector={
                "type": "clipboard_has_content",
                "pattern": r"^[a-f0-9]{32}$",  # OpenWeatherMap API Key格式
            },
            alternative_methods=[
                {
                    "title": "使用免费方案",
                    "description": "不需要API Key，使用Open-Meteo等公开服务",
                    "action": "switch_to_free",
                },
            ],
        )
        
        # 高德开放平台引导
        self._website_guides["amap_signup"] = WebsiteGuide(
            url="https://lbs.amap.com/dev/key/app",
            highlight_script="""
// 高亮创建应用按钮
document.querySelector('.create-key-btn')?.style.setProperty('background', '#1989fa', 'important');
""",
            steps=[
                {
                    "title": "创建应用",
                    "description": "点击创建应用按钮",
                    "selector": ".create-key-btn",
                    "action": "click",
                },
                {
                    "title": "填写应用信息",
                    "description": "输入应用名称（可随意填写）",
                    "selector": "input[name='app_name']",
                    "action": "input",
                },
                {
                    "title": "选择服务类型",
                    "description": "选择 Web 服务 API",
                    "selector": "select[name='service_type']",
                    "action": "select",
                },
                {
                    "title": "获取Key",
                    "description": "复制生成的 Key",
                    "selector": ".key-value",
                    "action": "copy",
                },
            ],
            completion_detector={
                "type": "clipboard_has_content",
            },
        )
        
        # OpenAI Platform 引导
        self._website_guides["openai_signup"] = WebsiteGuide(
            url="https://platform.openai.com/api-keys",
            highlight_script="""
// 高亮创建按钮
document.querySelector('[data-testid="create-key-button"]')?.style.setProperty('transform', 'scale(1.05)', 'important');
""",
            steps=[
                {
                    "title": "点击创建",
                    "description": "点击 Create new secret key 按钮",
                    "selector": "[data-testid='create-key-button']",
                    "action": "click",
                },
                {
                    "title": "复制Key",
                    "description": "在弹出框中复制API Key",
                    "selector": ".key-display",
                    "action": "copy",
                },
            ],
            completion_detector={
                "type": "clipboard_has_content",
                "pattern": r"sk-",  # OpenAI API Key格式
            },
            alternative_methods=[
                {
                    "title": "使用 Claude（备选）",
                    "description": "Anthropic 的 Claude 模型",
                    "url": "https://console.anthropic.com/settings/keys",
                },
                {
                    "title": "使用本地模型（免费）",
                    "description": "无需API Key，使用Ollama本地部署",
                    "action": "switch_to_local",
                },
            ],
        )
    
    def create_website_guide(
        self, 
        website: str, 
        goal: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[WebsiteGuide]:
        """
        创建网站引导
        
        Args:
            website: 网站URL
            goal: 目标标识符
        
        Returns:
            WebsiteGuide 或 None
        """
        # 查找匹配的引导
        guide = self._website_guides.get(f"{website}_{goal}")
        
        if guide is None:
            # 尝试模糊匹配
            for key, g in self._website_guides.items():
                if goal in key or key in goal:
                    guide = g
                    break
        
        if guide is None:
            # 生成通用引导
            return self._create_generic_guide(website, goal)
        
        return guide
    
    def _create_generic_guide(self, url: str, goal: str) -> WebsiteGuide:
        """创建通用网站引导"""
        return WebsiteGuide(
            url=url,
            highlight_script="""
// 通用高亮脚本
document.body.style.setProperty('outline', '3px solid #2196F3', 'important');
""",
            steps=[
                {
                    "title": "访问网站",
                    "description": f"打开 {url}",
                    "selector": "body",
                    "action": "visit",
                },
                {
                    "title": "找到目标",
                    "description": f"完成 {goal} 相关操作",
                    "selector": "",
                    "action": "manual",
                },
            ],
            completion_detector={
                "type": "manual_confirm",
            },
        )
    
    def get_guide_for_feature(self, feature_id: str) -> Optional[WebsiteGuide]:
        """
        获取功能对应的网站引导
        
        Args:
            feature_id: 功能标识符
        
        Returns:
            WebsiteGuide 或 None
        """
        # 映射功能到网站引导
        feature_to_guide = {
            "weather_api": "openweather_signup",
            "map_service": "amap_signup",
            "openai_api": "openai_signup",
        }
        
        guide_key = feature_to_guide.get(feature_id)
        if guide_key:
            return self._website_guides.get(guide_key)
        
        return None
    
    def generate_highlight_script(
        self, 
        selectors: List[str],
        color: str = "#00ff00"
    ) -> str:
        """
        生成高亮脚本
        
        Args:
            selectors: 要高亮的元素选择器列表
            color: 高亮颜色
        
        Returns:
            JavaScript脚本
        """
        script_lines = []
        
        for selector in selectors:
            script_lines.append(f"""
// 高亮: {selector}
const elements = document.querySelectorAll('{selector}');
elements.forEach(el => {{
    el.style.setProperty('border', '3px solid {color}', 'important');
    el.style.setProperty('box-shadow', '0 0 10px {color}', 'important');
}});
""")
        
        return "\n".join(script_lines)
    
    def create_clipboard_detector(
        self, 
        pattern: Optional[str] = None,
        expected_length: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        创建剪贴板检测器
        
        用于检测用户是否成功复制了内容
        
        Args:
            pattern: 期望的模式（正则表达式）
            expected_length: 期望的长度
        
        Returns:
            检测器配置
        """
        detector = {
            "type": "clipboard_has_content",
        }
        
        if pattern:
            detector["pattern"] = pattern
        
        if expected_length:
            detector["expected_length"] = expected_length
        
        return detector
    
    def get_alternative_methods(
        self, 
        feature_id: str
    ) -> List[Dict[str, Any]]:
        """
        获取替代方法
        
        当网站引导不可用时
        
        Args:
            feature_id: 功能标识符
        
        Returns:
            替代方法列表
        """
        alternatives = []
        
        if feature_id == "weather_api":
            alternatives = [
                {
                    "title": "Open-Meteo（无需注册）",
                    "description": "免费公开的天气API，无需注册",
                    "action": "switch_to_openmeteo",
                    "benefits": ["无需配置", "完全免费", "无限调用"],
                },
                {
                    "title": "使用历史数据",
                    "description": "使用系统内置的历史天气数据",
                    "action": "use_mock_data",
                    "benefits": ["完全免费", "无需网络"],
                    "limitations": ["数据不是实时的"],
                },
            ]
        elif feature_id == "map_service":
            alternatives = [
                {
                    "title": "OpenStreetMap",
                    "description": "免费开源的地图服务",
                    "action": "switch_to_osm",
                    "benefits": ["无需注册", "完全免费"],
                },
            ]
        elif feature_id == "openai_api":
            alternatives = [
                {
                    "title": "Claude API",
                    "description": "Anthropic 的 Claude 模型",
                    "url": "https://console.anthropic.com/settings/keys",
                    "benefits": ["强大的推理能力", "较长的上下文"],
                },
                {
                    "title": "本地模型 Ollama",
                    "description": "在本地运行AI模型",
                    "action": "setup_ollama",
                    "benefits": ["完全免费", "保护隐私"],
                    "limitations": ["需要本地GPU"],
                },
            ]
        
        return alternatives
    
    def register_website_guide(
        self, 
        guide_id: str, 
        guide: WebsiteGuide
    ):
        """
        注册网站引导
        
        Args:
            guide_id: 引导ID
            guide: 网站引导
        """
        self._website_guides[guide_id] = guide
    
    def get_supported_guides(self) -> List[str]:
        """获取支持的引导列表"""
        return list(self._website_guides.keys())


# 全局实例
_browser_guide: Optional[BrowserAutomationGuide] = None


def get_browser_automation_guide() -> BrowserAutomationGuide:
    """获取浏览器自动化引导全局实例"""
    global _browser_guide
    if _browser_guide is None:
        _browser_guide = BrowserAutomationGuide()
    return _browser_guide