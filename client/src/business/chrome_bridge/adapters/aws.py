"""
Aws Adapter - aws 网站适配器
======================================================

支持：
- 登录状态检测（通用：检查登录/登出按钮）
- 内容提取（通用：提取 title + body text）
- 会话复用：直接使用已登录的 Chrome
"""

from typing import Dict, Any
from business.chrome_bridge.website_adapter_base import BaseWebsiteAdapter


class AWSAdapter(BaseWebsiteAdapter):
    """"aws 网站适配器（通用实现）"""""

    def get_name(self) -> str:
        return "aws"

    def get_domains(self) -> list:
        return ['aws.amazon.com', 'console.aws.amazon.com']

    def get_homepage(self) -> str:
        return "https://aws.amazon.com"

    def get_login_url(self) -> str:
        return None  # 通用适配器不指定登录 URL

    async def check_login(self, cdp, page_id: str) -> Dict[str, Any]:
        """通用登录检测：检查页面是否有登出/登录相关元素"""
        try:
            # 检测登出按钮（已登录标志）
            has_logout = await cdp.evaluate(
                page_id,
                "!!document.querySelector('a[href*=\"logout\"], a[href*=\"sign-out\"], a[href*=\"sign_out\"')"
            )
            if has_logout:
                return {"logged_in": True, "method": "logout_button_check"}

            # 检测登录按钮（未登录标志）
            has_login = await cdp.evaluate(
                page_id,
                "!!document.querySelector('a[href*=\"login\"], a[href*=\"sign-in\"], button:contains(\"登录\"), button:contains(\"Sign in\")')"
            )
            if has_login:
                return {"logged_in": False, "method": "login_button_check"}

            # 检测用户头像（已登录标志）
            has_avatar = await cdp.evaluate(
                page_id,
                "!!document.querySelector('.avatar, [class*=\"avatar\"], img[alt*=\"profile\"')"
            )
            return {"logged_in": has_avatar, "method": "avatar_check"}
        except Exception as e:
            return {"logged_in": None, "error": str(e), "method": "generic"}

    async def extract_content(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """通用内容提取：提取 title + body text"""
        try:
            title = await cdp.evaluate(page_id, "document.title")
            text = await cdp.evaluate(page_id, "document.body.innerText?.slice(0, 3000) || ''")
            html_lang = await cdp.evaluate(page_id, "document.documentElement.lang || ''")
            return {
                "type": "generic",
                "title": title,
                "text": text,
                "lang": html_lang,
                "extractor": "generic_aws",
            }
        except Exception as e:
            return {"type": "generic", "error": str(e), "extractor": "generic_aws"}
