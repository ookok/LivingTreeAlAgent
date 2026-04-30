"""
Adapter Generator - 适配器批量生成器
============================================

根据 website_adapter_registry.py 中的 WEBSITE_REGISTRY_DATA，
批量生成 80+ 个网站适配器文件。

生成逻辑：
- 若适配器已手动实现（如 github.py、stackoverflow.py），跳过
- 其余网站生成通用适配器（继承 BaseWebsiteAdapter，含通用实现）
- 通用实现包括：登录检测（检查登录/登出按钮）、内容提取（提取 title + body text）
"""

import os
import sys
import importlib

# 添加 adapters 目录到 sys.path
ADAPTERS_DIR = os.path.dirname(os.path.abspath(__file__))
if ADAPTERS_DIR not in sys.path:
    sys.path.insert(0, ADAPTERS_DIR)

# 导入注册表数据
from business.chrome_bridge.website_adapter_registry import WEBSITE_REGISTRY_DATA


# 适配器模板
ADAPTER_TEMPLATE = '''\
"""
{class_name} - {name} 网站适配器
======================================{separator}

支持：
- 登录状态检测（通用：检查登录/登出按钮）
- 内容提取（通用：提取 title + body text）
- 会话复用：直接使用已登录的 Chrome
"""

from typing import Dict, Any
from business.chrome_bridge.website_adapter_base import BaseWebsiteAdapter


class {class_name}(BaseWebsiteAdapter):
    """{name} 网站适配器（通用实现）"""

    def get_name(self) -> str:
        return "{name}"

    def get_domains(self) -> list:
        return {domains}

    def get_homepage(self) -> str:
        return "{homepage}"

    def get_login_url(self) -> str:
        return None  # 通用适配器不指定登录 URL

    async def check_login(self, cdp, page_id: str) -> Dict[str, Any]:
        """通用登录检测：检查页面是否有登录/登出相关元素"""
        try:
            # 检测登出按钮（已登录标志）
            has_logout = await cdp.evaluate(
                page_id,
                "!!document.querySelector('a[href*=\\"logout\\"], a[href*=\\"sign-out\\"], a[href*=\\"sign_out\\"]')"
            )
            if has_logout:
                return {{"logged_in": True, "method": "logout_button_check"}}

            # 检测登录按钮（未登录标志）
            has_login = await cdp.evaluate(
                page_id,
                "!!document.querySelector('a[href*=\\"login\\"], a[href*=\\"sign-in\\"], button:contains(\\"登录\\"), button:contains(\\"Sign in\\")')"
            )
            if has_login:
                return {{"logged_in": False, "method": "login_button_check"}}

            # 检测用户头像（已登录标志）
            has_avatar = await cdp.evaluate(
                page_id,
                "!!document.querySelector('.avatar, [class*=\\"avatar\\"], img[alt*=\\"profile\\"]')"
            )
            return {{"logged_in": has_avatar, "method": "avatar_check"}}
        except Exception as e:
            return {{"logged_in": None, "error": str(e), "method": "generic"}}

    async def extract_content(self, cdp, page_id: str, url: str) -> Dict[str, Any]:
        """通用内容提取：提取 title + body text"""
        try:
            title = await cdp.evaluate(page_id, "document.title")
            text = await cdp.evaluate(page_id, "document.body.innerText?.slice(0, 3000) || ''")
            html_lang = await cdp.evaluate(page_id, "document.documentElement.lang || ''")
            return {{
                "type": "generic",
                "title": title,
                "text": text,
                "lang": html_lang,
                "extractor": "generic_{name}",
            }}
        except Exception as e:
            return {{"type": "generic", "error": str(e), "extractor": "generic_{name}"}}
'''


def generate_adapter_module(name: str, class_name: str, domains: list, homepage: str) -> str:
    """生成适配器模块代码"""
    separator = "=" * (len(class_name) + len(" 网站适配器") + 6)
    return ADAPTER_TEMPLATE.format(
        name=name,
        class_name=class_name,
        domains=domains,
        homepage=homepage,
        separator=separator,
    )


def main():
    """主函数：批量生成适配器文件"""
    generated = 0
    skipped = 0
    failed = 0

    for entry in WEBSITE_REGISTRY_DATA:
        name = entry["name"]
        module = entry["module"]
        class_name = entry["class"]
        domains = entry["domains"]
        homepage = f"https://{domains[0]}" if domains else ""

        filepath = os.path.join(ADAPTERS_DIR, f"{module}.py")

        # 跳过已手动实现的适配器
        if os.path.exists(filepath):
            print(f"⏭ 跳过（已存在）: {name} -> {module}.py")
            skipped += 1
            continue

        # 生成适配器文件
        try:
            code = generate_adapter_module(name, class_name, domains, homepage)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)
            print(f"✅ 生成: {name} -> {module}.py")
            generated += 1
        except Exception as e:
            print(f"❌ 失败: {name} -> {e}")
            failed += 1

    print(f"\n📊 完成：生成 {generated} 个，跳过 {skipped} 个，失败 {failed} 个")


if __name__ == "__main__":
    main()
