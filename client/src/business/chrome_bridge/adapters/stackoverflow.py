"""
StackOverflow Adapter - StackOverflow 网站适配器
==================================================

支持：
- 登录状态检测（检查顶部栏是否有用户头像/名称）
- 内容提取：问题、回答、标签、投票数
- 会话复用：直接使用已登录的 Chrome
"""

from typing import Dict, Any
from loguru import logger

from business.chrome_bridge.website_adapter_base import BaseWebsiteAdapter


class StackOverflowAdapter(BaseWebsiteAdapter):
    """StackOverflow 网站适配器"""

    def get_name(self) -> str:
        return "stackoverflow"

    def get_domains(self) -> list:
        return ["stackoverflow.com"]

    def get_homepage(self) -> str:
        return "https://stackoverflow.com"

    def get_login_url(self) -> str:
        return "https://stackoverflow.com/users/login"

    async def check_login(self, cdp, page_id: str) -> Dict[str, Any]:
        """
        检测 StackOverflow 登录状态

        登录后：
        - 顶部有用户头像（.s-topbar--avatar）
        - 或顶部有登出链接
        """
        try:
            # 检查是否有用户头像（登录标志）
            has_avatar = await cdp.evaluate(
                page_id,
                """
                !!document.querySelector('.s-topbar--avatar')
                || !!document.querySelector('[data-controller="UserController"]')
                || !!document.querySelector('.s-user-card--link')
                """
            )

            if has_avatar:
                # 获取用户名
                username = await cdp.evaluate(
                    page_id,
                    """
                    document.querySelector('.s-user-card--link')?.innerText?.trim()
                    || document.querySelector('.s-topbar--avatar')?.getAttribute('title')?.trim()
                    || ''
                    """
                )
                return {
                    "logged_in": True,
                    "username": username,
                    "method": "avatar_check",
                }

            # 检查是否有登录按钮（未登录标志）
            has_login_btn = await cdp.evaluate(
                page_id,
                """!!document.querySelector('a[href*="login"]')"""
            )
            return {
                "logged_in": not has_login_btn,
                "method": "login_button_check",
            }

        except Exception as e:
            logger.bind(module="StackOverflowAdapter").error(f"登录检测失败: {e}")
            return {"logged_in": None, "error": str(e)}

    async def extract_content(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """
        提取 StackOverflow 页面内容

        根据 URL 模式判断页面类型：
        - 问题页面：/questions/{id}/
        - 用户页面：/users/{id}/
        - 标签页面：/tags/
        """
        import re

        if re.search(r"/questions/\d+/", url):
            return await self._extract_question(cdp, page_id, url)
        elif re.search(r"/users/\d+/", url):
            return await self._extract_user(cdp, page_id, url)
        elif "/tags" in url:
            return await self._extract_tag(cdp, page_id, url)
        else:
            return await self._extract_generic(cdp, page_id, url)

    async def _extract_question(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """提取问题页面内容"""
        js = """
        (function() {
            const result = {};
            // 问题标题
            result.title = document.querySelector('.question-hyperlink')?.innerText?.trim() || '';
            // 问题描述
            result.body = document.querySelector('.js-post-body')?.innerText?.slice(0, 5000) || '';
            // 投票数
            const voteText = document.querySelector('.js-vote-count')?.innerText || '0';
            result.votes = parseInt(voteText.replace(/,/g, '')) || 0;
            // 标签
            result.tags = Array.from(document.querySelectorAll('.post-taglist a')).map(el => el.innerText?.trim());
            // 回答数
            const answersText = document.querySelector('#answers-header h2')?.innerText || '';
            const answersMatch = answersText.match(/\\d+/);
            result.answer_count = answersMatch ? parseInt(answersMatch[0]) : 0;
            // 是否有已接受的回答
            result.has_accepted = !!document.querySelector('.accepted-answer');
            // 提问者
            result.asker = document.querySelector('.user-details a')?.innerText?.trim() || '';
            return result;
        })()
        """
        data = await cdp.evaluate(page_id, js)
        data["url"] = url
        data["type"] = "question"
        return data

    async def _extract_user(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """提取用户页面内容"""
        js = """
        (function() {
            const result = {};
            result.username = document.querySelector('.user-card-name')?.innerText?.trim() || '';
            result.reputation = document.querySelector('.fs-headline1')?.innerText?.replace(/,/g, '') || '0';
            result.gold_badges = document.querySelector('.badge1+ .badge-count')?.innerText || '0';
            result.silver_badges = document.querySelector('.badge2+ .badge-count')?.innerText || '0';
            result.bronze_badges = document.querySelector('.badge3+ .badge-count')?.innerText || '0';
            // 回答数
            const stats = document.querySelectorAll('.user-stats td');
            for (let i = 0; i < stats.length; i++) {
                if (stats[i].innerText?.includes('answers')) {
                    result.answer_count = parseInt((stats[i+1]?.innerText || '0').replace(/,/g, ''));
                    break;
                }
            }
            return result;
        })()
        """
        data = await cdp.evaluate(page_id, js)
        data["url"] = url
        data["type"] = "user"
        return data

    async def _extract_tag(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """提取标签页面内容"""
        js = """
        (function() {
            const result = {tags: []};
            const tagEls = document.querySelectorAll('.tagged');
            result.tags = Array.from(tagEls).map(el => ({
                name: el.querySelector('.post-tag')?.innerText?.trim() || '',
                count: parseInt((el.querySelector('.item-multiplier')?.innerText || '0').replace(/,/g, '')),
            }));
            return result;
        })()
        """
        data = await cdp.evaluate(page_id, js)
        data["url"] = url
        data["type"] = "tag_list"
        return data

    async def _extract_generic(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """通用提取"""
        title = await cdp.evaluate(page_id, "document.title")
        text = await cdp.evaluate(page_id, "document.body.innerText?.slice(0, 3000) || ''")
        return {
            "url": url,
            "type": "generic",
            "title": title,
            "text": text,
        }
