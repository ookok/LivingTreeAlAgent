"""
智能代理服务器 (SmartProxy)
===========================

核心思想：通过本地代理实现网络层拦截，向政府网站注入AI助手

功能：
1. 智能注入：对gov.cn网站注入填表助手
2. P2P缓存：优先从P2P网络获取缓存
3. 内容过滤：识别并处理环评相关页面
4. 访问日志：记录所有访问用于审计
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse, parse_qs


class RequestType(Enum):
    """请求类型"""
    HTML = "html"
    CSS = "css"
    JS = "js"
    IMAGE = "image"
    FONT = "font"
    OTHER = "other"
    XMLHttpRequest = "xhr"


@dataclass
class ProxyRequest:
    """代理请求"""
    url: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[bytes] = None
    request_type: RequestType = RequestType.OTHER
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def domain(self) -> str:
        return urlparse(self.url).netloc

    @property
    def path(self) -> str:
        return urlparse(self.url).path


@dataclass
class ProxyResponse:
    """代理响应"""
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    content_type: str = ""
    from_cache: bool = False

    @property
    def is_html(self) -> bool:
        return "text/html" in self.content_type


@dataclass
class ProxyRule:
    """代理规则"""
    name: str
    pattern: str  # URL模式（正则）
    action: str   # inject / block / cache / modify
    priority: int = 0
    config: Dict[str, Any] = field(default_factory=dict)


class SmartProxyHandler:
    """
    智能代理处理器

    核心能力：
    1. URL模式匹配
    2. 内容注入
    3. 缓存管理
    4. 日志记录
    """

    def __init__(self):
        self.rules: List[ProxyRule] = []
        self.cache: Dict[str, ProxyResponse] = {}
        self.access_log: List[Dict] = []
        self.p2p_network = None  # P2P网络引用

        # 内置政府网站注入规则
        self._register_gov_rules()

    def _register_gov_rules(self):
        """注册政府网站注入规则"""
        # 环保局网站 - 注入填表助手
        self.rules.append(ProxyRule(
            name="环保局的填表助手",
            pattern=r"sthjj\.gov\.cn|mee\.gov\.cn|huanbao.*\.gov",
            action="inject",
            priority=10,
            config={
                "injection_type": "form_assistant",
                "assistant_url": "http://localhost:9999/hyper-assistant.js"
            }
        ))

        # 排污许可平台
        self.rules.append(ProxyRule(
            name="排污许可智能助手",
            pattern=r"permit\.mee\.gov\.cn|pollution.*permit",
            action="inject",
            priority=10,
            config={
                "injection_type": "permit_assistant",
                "auto_fill": True
            }
        ))

        # 全国环评平台
        self.rules.append(ProxyRule(
            name="环评报告助手",
            pattern=r"eia\.mee\.gov\.cn|china-eia.*\.com",
            action="inject",
            priority=10,
            config={
                "injection_type": "eia_assistant",
                "upload_help": True
            }
        ))

        # 静态资源 - 缓存
        self.rules.append(ProxyRule(
            name="静态资源缓存",
            pattern=r"\.(css|js|png|jpg|jpeg|gif|ico|woff|woff2|ttf|svg)$",
            action="cache",
            priority=1,
            config={"cache_ttl": 3600 * 24}  # 24小时
        ))

        # 广告拦截
        self.rules.append(ProxyRule(
            name="广告拦截",
            pattern=r"analytics|tracking|ads|doubleclick",
            action="block",
            priority=100
        ))

    def set_p2p_network(self, p2p_network):
        """设置P2P网络引用"""
        self.p2p_network = p2p_network

    async def handle_request(self, request: ProxyRequest) -> ProxyResponse:
        """
        处理代理请求

        Args:
            request: 代理请求

        Returns:
            ProxyResponse: 代理响应
        """
        # 1. 记录访问日志
        self._log_access(request)

        # 2. 匹配规则
        matched_rule = self._match_rule(request.url)

        if matched_rule and matched_rule.action == "block":
            return ProxyResponse(
                status_code=403,
                body=b"Blocked by HyperOS"
            )

        # 3. 尝试从P2P缓存获取
        if matched_rule and matched_rule.action == "cache":
            cached = await self._get_from_cache(request.url)
            if cached:
                return cached

        # 4. 获取原始内容
        response = await self._fetch_original(request)

        # 5. 如果匹配注入规则，注入脚本
        if matched_rule and matched_rule.action == "inject":
            response = await self._inject_script(response, matched_rule)

        # 6. 如果匹配缓存规则，存入缓存
        if matched_rule and matched_rule.action == "cache":
            await self._save_to_cache(request.url, response)

        return response

    def _match_rule(self, url: str) -> Optional[ProxyRule]:
        """匹配规则"""
        matched = None
        for rule in sorted(self.rules, key=lambda r: r.priority, reverse=True):
            if re.search(rule.pattern, url, re.IGNORECASE):
                matched = rule
        return matched

    def _log_access(self, request: ProxyRequest):
        """记录访问日志"""
        self.access_log.append({
            "url": request.url,
            "domain": request.domain,
            "method": request.method,
            "request_type": request.request_type.value,
            "timestamp": request.timestamp.isoformat()
        })
        # 只保留最近1000条
        if len(self.access_log) > 1000:
            self.access_log = self.access_log[-1000:]

    async def _get_from_cache(self, url: str) -> Optional[ProxyResponse]:
        """从缓存获取"""
        if url in self.cache:
            cached = self.cache[url]
            cached.from_cache = True
            return cached
        return None

    async def _save_to_cache(self, url: str, response: ProxyResponse):
        """存入缓存"""
        # 只缓存HTML和静态资源
        if response.is_html or response.content_type.startswith(("image/", "font/", "text/css")):
            self.cache[url] = response

    async def _fetch_original(self, request: ProxyRequest) -> ProxyResponse:
        """获取原始内容"""
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=request.method,
                    url=request.url,
                    headers=request.headers,
                    data=request.body,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    body = await resp.read()
                    headers = dict(resp.headers)

                    content_type = headers.get("Content-Type", "")

                    return ProxyResponse(
                        status_code=resp.status,
                        headers=headers,
                        body=body,
                        content_type=content_type
                    )
        except Exception as e:
            return ProxyResponse(
                status_code=502,
                body=f"Proxy Error: {str(e)}".encode()
            )

    async def _inject_script(
        self,
        response: ProxyResponse,
        rule: ProxyRule
    ) -> ProxyResponse:
        """向响应注入脚本"""
        if not response.is_html:
            return response

        html = response.body.decode("utf-8", errors="ignore")

        # 根据注入类型选择脚本
        injection_type = rule.config.get("injection_type", "default")

        if injection_type == "form_assistant":
            script = self._generate_form_assistant_script()
        elif injection_type == "permit_assistant":
            script = self._generate_permit_assistant_script()
        elif injection_type == "eia_assistant":
            script = self._generate_eia_assistant_script()
        else:
            script = self._generate_default_script()

        # 注入到</body>前
        if "</body>" in html:
            html = html.replace("</body>", script + "</body>")
        elif "</html>" in html:
            html = html.replace("</html>", script + "</html>")

        response.body = html.encode("utf-8")
        return response

    def _generate_form_assistant_script(self) -> str:
        """生成填表助手脚本"""
        return '''
<script src="http://localhost:9999/hyper-assistant.js"></script>
<script>
(function() {
    // 连接WebSocket到Python端
    const ws = new WebSocket('ws://localhost:8765');
    ws.onopen = () => console.log('HyperOS Connected');
    ws.onerror = (e) => console.error('WS Error', e);

    // 检测表单
    const checkForms = () => {
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            // 通知Python检测到表单
            ws.send(JSON.stringify({
                type: 'form_detected',
                url: window.location.href,
                form_id: form.id || form.name || 'anonymous',
                fields: Array.from(form.elements).map(e => ({
                    name: e.name,
                    type: e.type,
                    tagName: e.tagName
                }))
            }));
        });
    };

    // 页面加载完成后检测
    if (document.readyState === 'complete') {
        checkForms();
    } else {
        window.addEventListener('load', checkForms);
    }

    // 接收Python端消息
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'autofill') {
            // 自动填表
            data.fields.forEach(field => {
                const el = document.querySelector(`[name="${field.name}"]`);
                if (el) {
                    el.value = field.value;
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                }
            });
        }
    };

    window.HyperOS = {
        ws: ws,
        getPageContent: () => document.documentElement.outerHTML,
        getFormData: () => {
            const forms = document.querySelectorAll('form');
            return Array.from(forms).map(f => ({
                id: f.id,
                action: f.action,
                fields: Array.from(f.elements).map(e => ({
                    name: e.name,
                    value: e.value,
                    type: e.type
                }))
            }));
        }
    };
})();
</script>
'''

    def _generate_permit_assistant_script(self) -> str:
        """生成排污许可助手脚本"""
        return self._generate_form_assistant_script() + '''
<script>
window.HyperOS.permitMode = true;
window.HyperOS.getPermitData = async () => {
    // 提取许可证相关信息
    const tables = document.querySelectorAll('table');
    return {
        tables: tables.length,
        pollutants: Array.from(document.querySelectorAll('input[name*="pollutant"]')).map(e => e.value),
        emissions: Array.from(document.querySelectorAll('input[name*="emission"]')).map(e => parseFloat(e.value) || 0)
    };
};
</script>
'''

    def _generate_eia_assistant_script(self) -> str:
        """生成环评助手脚本"""
        return self._generate_form_assistant_script() + '''
<script>
window.HyperOS.eiaMode = true;
window.HyperOS.getEIAData = async () => {
    // 提取环评报告相关信息
    return {
        projectName: document.querySelector('[data-field="projectName"]')?.textContent || '',
        industryType: document.querySelector('[data-field="industryType"]')?.textContent || '',
        content: window.HyperOS.getPageContent()
    };
};
</script>
'''

    def _generate_default_script(self) -> str:
        """生成默认脚本"""
        return '''
<script src="http://localhost:9999/hyper-assistant.js"></script>
'''


class SmartProxy:
    """
    智能代理服务器

    使用 asyncio 实现高性能代理，支持：
    1. HTTP/HTTPS 转发
    2. 规则匹配
    3. 内容注入
    4. 缓存管理
    """

    def __init__(self, port: int = 8888):
        self.port = port
        self.handler = SmartProxyHandler()
        self.server = None
        self.is_running = False

    def set_p2p_network(self, p2p_network):
        """设置P2P网络"""
        self.handler.set_p2p_network(p2p_network)

    async def start(self):
        """启动代理服务器"""
        import aiohttp
        from aiohttp import web

        async def handle_request(request):
            # 构建代理请求
            url = str(request.url)
            headers = dict(request.headers)
            body = await request.read() if request.can_read_body else None

            # 确定请求类型
            if "text/html" in headers.get("Accept", ""):
                req_type = RequestType.HTML
            elif "javascript" in headers.get("Accept", ""):
                req_type = RequestType.JS
            elif "text/css" in headers.get("Accept", ""):
                req_type = RequestType.CSS
            else:
                req_type = RequestType.OTHER

            proxy_request = ProxyRequest(
                url=url,
                method=request.method,
                headers=headers,
                body=body,
                request_type=req_type
            )

            # 处理请求
            proxy_response = await self.handler.handle_request(proxy_request)

            # 构建响应
            response = web.Response(
                body=proxy_response.body,
                status=proxy_response.status_code,
                headers=proxy_response.headers
            )

            # 添加缓存标记
            if proxy_response.from_cache:
                response.headers["X-HyperOS-Cache"] = "HIT"

            return response

        # 创建应用
        app = web.Application()
        app.router.add_route('*', '/{path:.*}', handle_request)

        # 启动服务器
        self.server = web.AppRunner(app)
        await self.server.setup()
        site = web.TCPSite(self.server, '127.0.0.1', self.port)
        await site.start()
        self.is_running = True

        print(f"HyperOS SmartProxy running on http://127.0.0.1:{self.port}")

    async def stop(self):
        """停止代理服务器"""
        if self.server:
            await self.server.cleanup()
            self.is_running = False

    def get_access_log(self) -> List[Dict]:
        """获取访问日志"""
        return self.handler.access_log

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        return {
            "cached_urls": len(self.handler.cache),
            "cache_list": list(self.handler.cache.keys())[:10]
        }


# 全局实例
_proxy_instance: Optional[SmartProxy] = None


def get_smart_proxy(port: int = 8888) -> SmartProxy:
    """获取智能代理全局实例"""
    global _proxy_instance
    if _proxy_instance is None:
        _proxy_instance = SmartProxy(port)
    return _proxy_instance