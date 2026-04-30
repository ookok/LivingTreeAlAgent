"""
千问系列网站适配器
支持：千问官网、QuarkChat、通义千问等阿里系产品
"""
from typing import Dict, Any, List
from loguru import logger

from business.chrome_bridge.website_adapter_base import BaseWebsiteAdapter


class QianwenAdapter(BaseWebsiteAdapter):
    """千问系列网站适配器"""

    def get_name(self) -> str:
        return "qianwen"

    def get_domains(self) -> List[str]:
        return [
            "qianwen.com",
            "www.qianwen.com",
            "quark.sm.cn",
            "tongyi.aliyun.com"
        ]

    def get_homepage(self) -> str:
        return "https://www.qianwen.com"

    def get_login_url(self) -> str:
        return "https://www.qianwen.com/login"

    def get_login_selectors(self) -> Dict[str, str]:
        """返回千问登录表单的选择器"""
        return {
            "username": "input[type='text'], input[placeholder*='手机'], input[placeholder*='账号']",
            "password": "input[type='password'], input[placeholder*='密码']",
            "login_button": "button[type='submit'], .login-btn, .submit-btn",
            "verify_code": "input[placeholder*='验证码']"  # 可选
        }

    async def check_login(self, cdp, page_id: str) -> Dict[str, Any]:
        """检测千问登录状态"""
        try:
            # 检查是否存在用户头像或用户名元素
            has_avatar = await cdp.evaluate(
                page_id,
                """
                document.querySelector('.avatar, .user-avatar, [class*="avatar"]') !== null
                """
            )

            if has_avatar:
                # 获取用户名
                username = await cdp.evaluate(
                    page_id,
                    """
                    document.querySelector('.username, .user-name, [class*="username"]')?.innerText || ''
                    """
                )
                return {
                    "logged_in": True,
                    "username": username,
                    "extra": {}
                }
            else:
                return {"logged_in": False, "username": None, "extra": {}}
        except Exception as e:
            logger.bind(adapter="QianwenAdapter").error(f"检测登录状态失败: {e}")
            return {"logged_in": None, "error": str(e)}

    async def extract_content(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """提取千问页面内容"""
        # 判断页面类型
        if "quarkchat" in url or "chat" in url:
            return await self._extract_chat_content(cdp, page_id, url)
        elif "qianwen.com" in url:
            return await self._extract_homepage_content(cdp, page_id, url)
        else:
            return await self._extract_generic_content(cdp, page_id, url)

    async def _extract_chat_content(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """提取千问Chat页面的对话内容"""
        try:
            # 获取最后一条AI回复
            last_reply_js = """
            (function() {
                const messages = document.querySelectorAll('.chat-message, .message-item, [class*="message"]');
                if (messages.length === 0) return null;
                
                // 找到最后一条AI回复（通常包含特定class）
                for (let i = messages.length - 1; i >= 0; i--) {
                    const msg = messages[i];
                    if (msg.classList.contains('ai-message') || 
                        msg.querySelector('[class*="assistant"]') ||
                        !msg.querySelector('[class*="user"]')) {
                        return msg.innerText?.trim() || null;
                    }
                }
                return null;
            })();
            """

            last_reply = await cdp.evaluate(page_id, last_reply_js)

            # 获取所有对话
            all_messages_js = """
            Array.from(document.querySelectorAll('.chat-message, .message-item, [class*="message"]')).map(el => {
                const isUser = el.classList.contains('user-message') || el.querySelector('[class*="user"]');
                return {
                    role: isUser ? 'user' : 'assistant',
                    content: el.innerText?.trim() || ''
                };
            }).filter(msg => msg.content);
            """

            all_messages = await cdp.evaluate(page_id, all_messages_js)

            return {
                "type": "chat",
                "url": url,
                "last_reply": last_reply,
                "all_messages": all_messages[-10:] if all_messages else [],  # 最近10条
                "message_count": len(all_messages) if all_messages else 0
            }
        except Exception as e:
            logger.bind(adapter="QianwenAdapter").error(f"提取Chat内容失败: {e}")
            return {"type": "chat", "error": str(e)}

    async def _extract_homepage_content(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """提取千问首页内容"""
        title = await cdp.evaluate(page_id, "document.title")
        return {
            "type": "homepage",
            "url": url,
            "title": title,
            "page_type": "qianwen_homepage"
        }

    async def _extract_generic_content(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """通用内容提取"""
        html = await cdp.get_content(page_id)
        text = await cdp.get_text(page_id)
        title = await cdp.evaluate(page_id, "document.title")

        return {
            "type": "generic",
            "url": url,
            "title": title,
            "text": text[:2000],
            "html": html[:5000]
        }

    def get_anti_detect_js(self) -> str:
        """千问特定的反检测JS"""
        return """
        // 隐藏WebDriver痕迹
        Object.defineProperty(navigator, 'webdriver', {
            get: () => false
        });
        
        // 修改window.chrome对象
        window.chrome = {
            runtime: {}
        };
        """