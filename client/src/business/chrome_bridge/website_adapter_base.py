"""
Website Adapter Base - 网站适配器基类
============================================

定义所有网站适配器的统一接口，
提供通用实现（登录检测、JS 注入、内容提取等）。

所有 80+ 适配器都继承此类。
"""

import json
import re
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from loguru import logger


class BaseWebsiteAdapter(ABC):
    """
    网站适配器基类（抽象类）

    所有网站适配器必须继承此类并实现抽象方法。

    适配器职责：
    1. 声明支持的域名（get_domains）
    2. 检测登录状态（check_login）
    3. 提取页面内容（extract_content）
    4. 提供站点特定反检测 JS（get_anti_detect_js）
    """

    # ============================================================
    # 抽象方法（子类必须实现）
    # ============================================================

    @abstractmethod
    def get_name(self) -> str:
        """
        适配器名称

        Returns:
            名称字符串（如 "github", "stackoverflow"）
        """
        pass

    @abstractmethod
    def get_domains(self) -> List[str]:
        """
        支持的域名列表

        Returns:
            域名列表（如 ["github.com", "gist.github.com"]）

        匹配规则：URL 中包含任一域名即匹配
        """
        pass

    @abstractmethod
    def get_homepage(self) -> str:
        """
        网站首页 URL

        Returns:
            首页 URL（如 "https://github.com"）
        """
        pass

    @abstractmethod
    async def check_login(self, cdp, page_id: str) -> Dict[str, Any]:
        """
        检测登录状态

        Args:
            cdp: CDPHelper 实例
            page_id: 页面 ID

        Returns:
            登录状态字典，格式：
            {
                "logged_in": bool,
                "username": str or None,
                "avatar_url": str or None,
                "extra": {...}  # 额外信息
            }
        """
        pass

    @abstractmethod
    async def extract_content(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """
        提取页面内容

        Args:
            cdp: CDPHelper 实例
            page_id: 页面 ID
            url: 当前页面 URL

        Returns:
            提取的内容（结构化字典，格式因网站而异）

        示例（GitHub）：
        {
            "type": "repo",
            "repo_name": "...",
            "repo_description": "...",
            "stars": 123,
            ...
        }
        """
        pass

    def get_login_selectors(self) -> Dict[str, str]:
        """
        获取登录表单CSS选择器（可选重写）

        Returns:
            选择器字典，包含以下键（根据网站登录表单调整）：
            - username: 用户名输入框选择器
            - password: 密码输入框选择器
            - login_button: 登录按钮选择器
            - 其他网站特定的选择器

        默认实现：返回空字典，表示不支持自动登录
        """
        return {}

    # ============================================================
    # 可选重写方法（有默认实现）
    # ============================================================

    def get_anti_detect_js(self) -> str:
        """
        获取站点特定反检测 JS（可选重写）

        Returns:
            需要注入的 JS 代码（空字符串表示无）

        默认实现：返回空字符串
        子类可重写以添加站点特定反检测逻辑
        """
        return ""

    def get_login_url(self) -> Optional[str]:
        """
        获取登录页面 URL（可选重写）

        Returns:
            登录页面 URL，或 None（不需要登录）
        """
        return None

    def get_priority(self) -> int:
        """
        适配器优先级（用于同名域名冲突解决）

        Returns:
            优先级（数字越小优先级越高，默认 100）
        """
        return 100

    def supports_url(self, url: str) -> bool:
        """
        检测是否支持该 URL

        Args:
            url: 目标 URL

        Returns:
            是否支持
        """
        domains = self.get_domains()
        return any(d in url for d in domains)

    # ============================================================
    # 通用工具方法（子类可调用）
    # ============================================================

    async def _evaluate(self, cdp, page_id: str, expression: str) -> Any:
        """在页面中执行 JS（封装）"""
        return await cdp.evaluate(page_id, expression)

    async def _get_text(self, cdp, page_id: str, selector: str) -> str:
        """获取元素文本"""
        return await self._evaluate(
            cdp, page_id,
            f"document.querySelector('{selector}')?.innerText || ''"
        )

    async def _get_html(self, cdp, page_id: str, selector: str) -> str:
        """获取元素 HTML"""
        return await self._evaluate(
            cdp, page_id,
            f"document.querySelector('{selector}')?.innerHTML || ''"
        )

    async def _get_attribute(self, cdp, page_id: str, selector: str, attr: str) -> str:
        """获取元素属性"""
        return await self._evaluate(
            cdp, page_id,
            f"document.querySelector('{selector}')?.getAttribute('{attr}') || ''"
        )

    async def _get_all_texts(self, cdp, page_id: str, selector: str) -> List[str]:
        """获取所有匹配元素的文本"""
        js = f"""
        Array.from(document.querySelectorAll('{selector}')).map(el => el.innerText?.trim() || '')
        """
        result = await self._evaluate(cdp, page_id, js)
        return result if isinstance(result, list) else []

    async def _wait_for_selector(self, cdp, page_id: str, selector: str, timeout: float = 5.0):
        """等待选择器出现"""
        js = f"""
        new Promise((resolve) => {{
            const check = () => {{
                if (document.querySelector('{selector}')) {{
                    resolve(true);
                }} else {{
                    setTimeout(check, 100);
                }}
            }};
            check();
        }})
        """
        try:
            await cdp.evaluate(page_id, js)
        except Exception:
            pass

    def _parse_number(self, text: str) -> int:
        """
        解析数字字符串（处理 "1.2k", "3.4m" 等格式）

        Args:
            text: 数字字符串

        Returns:
            整数
        """
        if not text:
            return 0
        text = text.strip().upper().replace(",", "")
        match = re.match(r"([\d.]+)\s*([KMB])?", text)
        if not match:
            try:
                return int(text)
            except ValueError:
                return 0
        num = float(match.group(1))
        suffix = match.group(2)
        if suffix == "K":
            num *= 1000
        elif suffix == "M":
            num *= 1000000
        elif suffix == "B":
            num *= 1000000000
        return int(num)

    # ============================================================
    # 元信息
    # ============================================================

    def get_meta(self) -> Dict[str, Any]:
        """
        获取适配器元信息

        Returns:
            元信息字典
        """
        return {
            "name": self.get_name(),
            "domains": self.get_domains(),
            "homepage": self.get_homepage(),
            "login_url": self.get_login_url(),
            "priority": self.get_priority(),
            "supports_login_check": True,
            "supports_content_extraction": True,
        }

    def __str__(self):
        return f"WebsiteAdapter({self.get_name()}, domains={self.get_domains()})"

    def __repr__(self):
        return self.__str__()
