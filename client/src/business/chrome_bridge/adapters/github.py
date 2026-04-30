"""
GitHub Adapter - GitHub 网站适配器
======================================

支持：
- 登录状态检测（检查右上角是否有用户头像）
- 内容提取：仓库信息、用户信息、Issue、PR 等
- 会话复用：直接使用已登录的 Chrome
"""

import re
from typing import Dict, Any
from loguru import logger

from business.chrome_bridge.website_adapter_base import BaseWebsiteAdapter


class GitHubAdapter(BaseWebsiteAdapter):
    """GitHub 网站适配器"""

    def get_name(self) -> str:
        return "github"

    def get_domains(self) -> list:
        return ["github.com", "gist.github.com"]

    def get_homepage(self) -> str:
        return "https://github.com"

    def get_login_url(self) -> str:
        return "https://github.com/login"

    async def check_login(self, cdp, page_id: str) -> Dict[str, Any]:
        """
        检测 GitHub 登录状态

        GitHub 登录后：
        - 右上角有用户头像（.AppHeader-user）
        - 或页面有 /settings 链接
        """
        try:
            # 检查是否有用户头像（登录标志）
            has_avatar = await cdp.evaluate(
                page_id,
                """
                !!document.querySelector('.AppHeader-user .avatar')
                || !!document.querySelector('[data-test-selector="app-header-user-menu-avatar"]')
                || !!document.querySelector('.header-nav-current-user')
                """
            )

            if has_avatar:
                # 获取用户名
                username = await cdp.evaluate(
                    page_id,
                    """
                    document.querySelector('[data-test-selector="app-header-user-menu-avatar"]')?.alt
                    || document.querySelector('.AppHeader-user .avatar')?.alt
                    || ''
                    """
                )
                return {
                    "logged_in": True,
                    "username": username.strip("@") if username else None,
                    "method": "avatar_check",
                }

            # 检查是否有登录按钮（未登录标志）
            has_login_btn = await cdp.evaluate(
                page_id,
                """!!document.querySelector('a[href="/login"]')"""
            )
            return {
                "logged_in": not has_login_btn,
                "method": "login_button_check",
            }

        except Exception as e:
            logger.bind(module="GitHubAdapter").error(f"登录检测失败: {e}")
            return {"logged_in": None, "error": str(e)}

    async def extract_content(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """
        提取 GitHub 页面内容

        根据 URL 模式判断页面类型，分别提取：
        - 仓库首页：名称、描述、Star/Fork 数、README
        - 用户主页：用户名、仓库数、粉丝数
        - Issue/PR：标题、内容、状态
        """
        # 判断页面类型
        if "/pull/" in url:
            return await self._extract_pr(cdp, page_id, url)
        elif "/issue/" in url:
            return await self._extract_issue(cdp, page_id, url)
        elif re.search(r"/tree/|/blob/", url):
            return await self._extract_code(cdp, page_id, url)
        elif re.match(r"https?://github\.com/[^/]+/[^/]+/?$", url):
            return await self._extract_repo(cdp, page_id, url)
        elif re.match(r"https?://github\.com/[^/]+/?$", url):
            return await self._extract_user(cdp, page_id, url)
        else:
            return await self._extract_generic(cdp, page_id, url)

    async def _extract_repo(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """提取仓库信息"""
        js = """
        (function() {
            const result = {};
            // 仓库名
            result.name = document.querySelector('[itemprop="name"]')?.innerText?.trim() || '';
            // 描述
            result.description = document.querySelector('[itemprop="description"]')?.innerText?.trim() || '';
            // Star 数
            const starText = document.querySelector('#repository-container-header a[href$="/stargazers"]')?.innerText || '';
            result.stars = parseInt(starText.replace(/,/g, '')) || 0;
            // Fork 数
            const forkText = document.querySelector('#repository-container-header a[href$="/forks"]')?.innerText || '';
            result.forks = parseInt(forkText.replace(/,/g, '')) || 0;
            // 主要语言
            result.language = document.querySelector('[itemprop="programmingLanguage"]')?.innerText?.trim() || '';
            // README 前 2000 字符
            result.readme = document.querySelector('article.markdown-body')?.innerText?.slice(0, 2000) || '';
            return result;
        })()
        """
        data = await cdp.evaluate(page_id, js)
        data["url"] = url
        data["type"] = "repo"
        return data

    async def _extract_user(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """提取用户信息"""
        js = """
        (function() {
            const result = {};
            result.username = document.querySelector('.vcard-username')?.innerText?.trim() || '';
            result.name = document.querySelector('.vcard-fullname')?.innerText?.trim() || '';
            result.bio = document.querySelector('.user-profile-bio')?.innerText?.trim() || '';
            const stats = document.querySelectorAll('.vcard-stats a');
            result.repos = parseInt((stats[0]?.innerText || '').replace(/,/g, '')) || 0;
            result.followers = parseInt((stats[1]?.innerText || '').replace(/,/g, '')) || 0;
            result.following = parseInt((stats[2]?.innerText || '').replace(/,/g, '')) || 0;
            return result;
        })()
        """
        data = await cdp.evaluate(page_id, js)
        data["url"] = url
        data["type"] = "user"
        return data

    async def _extract_issue(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """提取 Issue 内容"""
        js = """
        (function() {
            const result = {};
            result.title = document.querySelector('.js-issue-title')?.innerText?.trim() || '';
            result.state = document.querySelector('.State')?.innerText?.trim() || '';
            result.body = document.querySelector('.comment-body')?.innerText?.slice(0, 3000) || '';
            result.labels = Array.from(document.querySelectorAll('.IssueLabel')).map(el => el.innerText?.trim());
            return result;
        })()
        """
        data = await cdp.evaluate(page_id, js)
        data["url"] = url
        data["type"] = "issue"
        return data

    async def _extract_pr(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """提取 PR 内容"""
        js = """
        (function() {
            const result = {};
            result.title = document.querySelector('.js-issue-title')?.innerText?.trim() || '';
            result.state = document.querySelector('.State')?.innerText?.trim() || '';
            result.body = document.querySelector('.comment-body')?.innerText?.slice(0, 3000) || '';
            return result;
        })()
        """
        data = await cdp.evaluate(page_id, js)
        data["url"] = url
        data["type"] = "pr"
        return data

    async def _extract_code(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """提取代码文件内容"""
        js = """
        (function() {
            const result = {};
            result.file_path = document.querySelector('.file-header')?.getAttribute('data-path') || '';
            result.content = document.querySelector('.blob-code-content')?.innerText?.slice(0, 5000) || '';
            result.language = document.querySelector('.blob-code-content')?.closest('[data-language]')?.getAttribute('data-language') || '';
            return result;
        })()
        """
        data = await cdp.evaluate(page_id, js)
        data["url"] = url
        data["type"] = "code"
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

    def get_login_selectors(self) -> Dict[str, str]:
        """返回GitHub登录表单的选择器"""
        return {
            "username": "input[name='login'], input[id='login_field']",
            "password": "input[name='password'], input[id='password_field']",
            "login_button": "input[type='submit'][value='Sign in'], button[type='submit']",
            "remember_me": "input[name='remember_me']"
        }

    def get_anti_detect_js(self) -> str:
        """GitHub 特定反检测 JS"""
        return """
        // GitHub 特定：确保 logged_in 状态不被检测
        Object.defineProperty(document, 'cookie', {
            get: () => document.cookie,
            set: (val) => { document.cookie = val; return true; }
        });
        """
