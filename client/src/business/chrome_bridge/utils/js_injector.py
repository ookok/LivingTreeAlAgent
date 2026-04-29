"""
JS Injector - JavaScript 注入工具
======================================

用于在页面加载前/后注入 JavaScript 代码，
实现反检测、内容提取、DOM 操作等功能。

注入时机：
- onNewDocument：页面加载前（反检测核心，需最早执行）
- onLoad：页面加载完成后（内容提取、DOM 操作）
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field


# ============================================================
# 预置反检测 JS 脚本
# ============================================================

ANTI_DETECT_JS = """
// ============================================================
// 反检测 JS 注入脚本
// 在页面加载前执行（onNewDocument）
// ============================================================

// 1. 覆盖 navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// 2. 删除 CDP 特征变量（window.cdc_adoQpoasnfa76pfcZLmcfl_*）
const cdpVars = Object.keys(window).filter(key => key.includes('cdc_adoQpoasnfa76pfcZLmcfl'));
for (const varName of cdpVars) {
    delete window[varName];
}

// 3. 覆盖 chrome 属性（Playwright/Puppeteer 特征）
if (window.chrome && window.chrome.runtime) {
    // 保留 chrome.runtime（许多网站需要），但清理其他特征
    const originalRuntime = window.chrome.runtime;
    // 不删除，但确保行为正常
}

// 4. 覆盖 permissions.query（反检测）
const origQuery = navigator.permissions.query;
navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        origQuery(parameters)
);

// 5. 覆盖 plugin 检测
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        {
            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
            description: "Portable Document Format",
            filename: "internal-pdf-viewer",
            length: 1,
            name: "Chrome PDF Plugin"
        },
        {
            0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format"},
            description: "Portable Document Format",
            filename: "internal-pdf-viewer",
            length: 1,
            name: "Chrome PDF Viewer"
        }
    ]
});

// 6. 覆盖 languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['zh-CN', 'zh', 'en-US', 'en']
});

// 7. 覆盖 hardwareConcurrency
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8
});

// 8. 覆盖 deviceMemory
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8
});

// 9. 覆盖 WebGL 指纹（可选，按需启用）
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    // 返回真实的渲染器/供应商信息
    if (parameter === 37445) {  // UNMASKED_RENDERER_WEBGL
        return 'ANGLE (Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)';
    }
    if (parameter === 37446) {  // UNMASKED_VENDOR_WEBGL
        return 'Google Inc.';
    }
    return getParameter(parameter);
};

// 10. 阻止 iframe 嵌套检测（可选）
if (window.self !== window.top) {
    // 在 iframe 中，不执行额外操作
}
"""

# 针对特定网站的反检测额外 JS
SITE_SPECIFIC_JS = {
    "github.com": """
        // GitHub 特定：确保 logged_in 状态不被检测
        Object.defineProperty(document, 'cookie', {
            get: () => document.cookie,
            set: (val) => document.cookie = val
        });
    """,
    "twitter.com": """
        // Twitter 特定：清理 Twitter 特有的自动化检测
        delete window.__nightmare;
        delete window._selenium;
        delete document.__selenium_unwrapped;
    """,
    "linkedin.com": """
        # LinkedIn 特定
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """,
}


@dataclass
class InjectScript:
    """注入脚本"""
    name: str
    source: str
    inject_at: str = "onNewDocument"  # onNewDocument | onLoad | onDomReady
    enabled: bool = True

    def to_cdp_params(self) -> Dict:
        """转换为 CDP 参数"""
        return {
            "source": self.source,
            "runAt": self.inject_at.replace("on", "").lower(),  # onNewDocument -> newdocument
        }


class JSInjector:
    """
    JavaScript 注入器

    管理注入脚本的生命周期：
    1. 注册脚本（按注入时机分类）
    2. 在适当时机通过 CDP 注入
    3. 支持动态启用/禁用脚本
    """

    def __init__(self):
        self._scripts: List[InjectScript] = []
        self._default_anti_detect = True
        self._site_specific_enabled = True

    # ============================================================
    # 脚本管理
    # ============================================================

    def register_script(self, script: InjectScript):
        """注册注入脚本"""
        self._scripts.append(script)

    def unregister_script(self, name: str):
        """取消注册脚本"""
        self._scripts = [s for s in self._scripts if s.name != name]

    def enable_default_anti_detect(self, enabled: bool = True):
        """启用/禁用默认反检测脚本"""
        self._default_anti_detect = enabled

    def enable_site_specific(self, enabled: bool = True):
        """启用/禁用站点特定反检测"""
        self._site_specific_enabled = enabled

    # ============================================================
    # 获取注入脚本（按域名）
    # ============================================================

    def get_scripts_for_url(self, url: str) -> List[InjectScript]:
        """
        根据 URL 获取需要注入的脚本列表

        Args:
            url: 目标 URL

        Returns:
            需要注入的脚本列表
        """
        scripts = []

        # 1. 默认反检测脚本
        if self._default_anti_detect:
            scripts.append(InjectScript(
                name="default_anti_detect",
                source=ANTI_DETECT_JS,
                inject_at="onNewDocument"
            ))

        # 2. 站点特定反检测
        if self._site_specific_enabled:
            for domain, js in SITE_SPECIFIC_JS.items():
                if domain in url:
                    scripts.append(InjectScript(
                        name=f"site_specific_{domain}",
                        source=js,
                        inject_at="onNewDocument"
                    ))

        # 3. 用户注册的脚本
        scripts.extend([s for s in self._scripts if s.enabled])

        return scripts

    def get_all_scripts(self) -> List[InjectScript]:
        """获取所有脚本"""
        scripts = []
        if self._default_anti_detect:
            scripts.append(InjectScript(
                name="default_anti_detect",
                source=ANTI_DETECT_JS,
                inject_at="onNewDocument"
            ))
        scripts.extend(self._scripts)
        return scripts

    # ============================================================
    # CDP 注入（通过 CDPHelper）
    # ============================================================

    async def inject_via_cdp(self, cdp_helper, page_id: str, url: str = None):
        """
        通过 CDP 注入脚本到页面

        Args:
            cdp_helper: CDPHelper 实例
            page_id: 页面 ID
            url: 目标 URL（用于站点特定脚本）
        """
        scripts = self.get_scripts_for_url(url) if url else self.get_all_scripts()

        for script in scripts:
            try:
                if script.inject_at == "onNewDocument":
                    # 通过 Page.addScriptToEvaluateOnNewDocument 注入
                    await cdp_helper.send_cdp_command(
                        page_id,
                        "Page.addScriptToEvaluateOnNewDocument",
                        {"source": script.source}
                    )
                elif script.inject_at == "onLoad":
                    # 通过 Runtime.evaluate 注入（页面加载后）
                    await cdp_helper.send_cdp_command(
                        page_id,
                        "Runtime.evaluate",
                        {
                            "expression": script.source,
                            "returnByValue": True
                        }
                    )
            except Exception as e:
                from loguru import logger
                logger.error(f"注入脚本失败 {script.name}: {e}")

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def wrap_in_iife(js_code: str) -> str:
        """将 JS 代码包装为 IIFE（立即执行函数）"""
        return f"""
        (function() {{
            {js_code}
        }})();
        """

    @staticmethod
    def create_cookie_injector(cookies: List[Dict]) -> str:
        """生成注入 Cookie 的 JS 代码"""
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        return f"""
        (function() {{
            const cookies = "{cookie_str}".split('; ');
            for (const cookie of cookies) {{
                document.cookie = cookie + '; path=/';
            }}
        }})();
        """

    @staticmethod
    def create_local_storage_injector(data: Dict[str, str]) -> str:
        """生成注入 LocalStorage 的 JS 代码"""
        data_json = json.dumps(data)
        return f"""
        (function() {{
            const data = {data_json};
            for (const [key, value] of Object.entries(data)) {{
                localStorage.setItem(key, value);
            }}
        }})();
        """


# ============================================================
# 全局单例
# ============================================================

_js_injector_instance: Optional[JSInjector] = None


def get_js_injector() -> JSInjector:
    """获取全局 JSInjector 实例"""
    global _js_injector_instance
    if _js_injector_instance is None:
        _js_injector_instance = JSInjector()
    return _js_injector_instance
