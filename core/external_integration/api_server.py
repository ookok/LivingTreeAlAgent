"""
REST API 服务器 - 外部应用调用 AI OS 的标准接口
=================================================

设计原则：
1. 简单易用 - 一个 HTTP POST 即可调用
2. 认证安全 - 支持 API Key 认证
3. 格式统一 - JSON 输入输出

API 端点:
- POST /api/v1/query           - 通用查询
- POST /api/v1/summarize       - 文档摘要
- POST /api/v1/polish          - 文本润色
- POST /api/v1/translate       - 翻译
- POST /api/vimplish           - 错别字纠正
- POST /api/v1/analyze         - 分析
- POST /api/v1/generate        - 内容生成
- GET  /api/v1/health          - 健康检查
- GET  /api/v1/capabilities    - 能力列表
"""

from core.logger import get_logger
logger = get_logger('external_integration.api_server')

import json
import time
import hashlib
import hmac
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from aiohttp import web
import asyncio


# ============== 数据模型 ==============

@dataclass
class APIRequest:
    """API 请求"""
    text: str
    context: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    api_key: Optional[str] = None


@dataclass
class APIResponse:
    """API 响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    request_id: Optional[str] = None
    elapsed_ms: Optional[float] = None


# ============== API 服务器 ==============

class ExternalAPIServer:
    """
    外部 API 服务器

    提供 REST API 供外部应用调用 AI OS 能力
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8898,
        api_keys: Optional[Dict[str, str]] = None,  # key -> name
        knowledge_base: Optional[Any] = None,  # AI OS 知识库引用
        llm_client: Optional[Any] = None,  # AI OS LLM 客户端
    ):
        self.host = host
        self.port = port
        self.api_keys = api_keys or {}  # 空字典表示无需认证
        self.knowledge_base = knowledge_base
        self.llm_client = llm_client

        self.app = web.Application()
        self._setup_routes()
        self._request_count = 0
        self._start_time = time.time()

    def _setup_routes(self):
        """设置路由"""
        routes = [
            # 通用端点
            ('POST', '/api/v1/query', self._handle_query),
            ('POST', '/api/v1/batch', self._handle_batch),

            # 专用端点
            ('POST', '/api/v1/summarize', self._handle_summarize),
            ('POST', '/api/v1/polish', self._handle_polish),
            ('POST', '/api/v1/translate', self._handle_translate),
            ('POST', '/api/v1/correct', self._handle_correct),
            ('POST', '/api/v1/analyze', self._handle_analyze),
            ('POST', '/api/v1/generate', self._handle_generate),

            # 系统端点
            ('GET', '/api/v1/health', self._handle_health),
            ('GET', '/api/v1/capabilities', self._handle_capabilities),

            # 根路径
            ('GET', '/', self._handle_root),
        ]

        for method, path, handler in routes:
            if method == 'POST':
                self.app.router.add_post(path, handler)
            else:
                self.app.router.add_get(path, handler)

    async def _check_auth(self, request: web.Request) -> Optional[str]:
        """检查认证，返回用户名或 None"""
        # 无 API Key 配置，跳过认证
        if not self.api_keys:
            return "anonymous"

        # 从 Header 获取 API Key
        api_key = request.headers.get('X-API-Key') or \
                  request.headers.get('Authorization', '').replace('Bearer ', '')

        if not api_key:
            return None

        return self.api_keys.get(api_key)

    async def _parse_request(self, request: web.Request) -> APIRequest:
        """解析请求"""
        try:
            data = await request.json()
        except json.JSONDecodeError:
            # 支持表单格式
            data = await request.post()

        return APIRequest(
            text=data.get('text', ''),
            context=data.get('context'),
            options=data.get('options', {}),
            api_key=request.headers.get('X-API-Key'),
        )

    def _make_response(self, success: bool, data: Any = None,
                      error: str = None, request_id: str = None) -> web.Response:
        """创建响应"""
        resp = APIResponse(
            success=success,
            data=data,
            error=error,
            request_id=request_id,
        )
        return web.json_response(asdict(resp))

    def _generate_request_id(self) -> str:
        """生成请求 ID"""
        return hashlib.md5(
            f"{time.time()}{id(self)}".encode()
        ).hexdigest()[:16]

    # ============== 处理器 ==============

    async def _handle_query(self, request: web.Request) -> web.Response:
        """通用查询"""
        auth = await self._check_auth(request)
        if auth is None:
            return self._make_response(False, error="需要 API Key")

        req = await self._parse_request(request)
        req_id = self._generate_request_id()

        # 调用知识库或 LLM
        result = await self._do_query(req, req_id)

        return self._make_response(True, data=result, request_id=req_id)

    async def _handle_summarize(self, request: web.Request) -> web.Response:
        """文档摘要"""
        auth = await self._check_auth(request)
        if auth is None:
            return self._make_response(False, error="需要 API Key")

        req = await self._parse_request(request)
        req_id = self._generate_request_id()

        # 调用 LLM 生成摘要
        result = await self._do_summarize(req, req_id)

        return self._make_response(True, data=result, request_id=req_id)

    async def _handle_polish(self, request: web.Request) -> web.Response:
        """文本润色"""
        auth = await self._check_auth(request)
        if auth is None:
            return self._make_response(False, error="需要 API Key")

        req = await self._parse_request(request)
        req_id = self._generate_request_id()

        result = await self._do_polish(req, req_id)

        return self._make_response(True, data=result, request_id=req_id)

    async def _handle_translate(self, request: web.Request) -> web.Response:
        """翻译"""
        auth = await self._check_auth(request)
        if auth is None:
            return self._make_response(False, error="需要 API Key")

        req = await self._parse_request(request)
        req_id = self._generate_request_id()

        target_lang = req.options.get('target_lang', 'en')
        result = await self._do_translate(req, req_id, target_lang)

        return self._make_response(True, data=result, request_id=req_id)

    async def _handle_correct(self, request: web.Request) -> web.Response:
        """错别字纠正"""
        auth = await self._check_auth(request)
        if auth is None:
            return self._make_response(False, error="需要 API Key")

        req = await self._parse_request(request)
        req_id = self._generate_request_id()

        result = await self._do_correct(req, req_id)

        return self._make_response(True, data=result, request_id=req_id)

    async def _handle_analyze(self, request: web.Request) -> web.Response:
        """分析"""
        auth = await self._check_auth(request)
        if auth is None:
            return self._make_response(False, error="需要 API Key")

        req = await self._parse_request(request)
        req_id = self._generate_request_id()

        result = await self._do_analyze(req, req_id)

        return self._make_response(True, data=result, request_id=req_id)

    async def _handle_generate(self, request: web.Request) -> web.Response:
        """内容生成"""
        auth = await self._check_auth(request)
        if auth is None:
            return self._make_response(False, error="需要 API Key")

        req = await self._parse_request(request)
        req_id = self._generate_request_id()

        result = await self._do_generate(req, req_id)

        return self._make_response(True, data=result, request_id=req_id)

    async def _handle_batch(self, request: web.Request) -> web.Response:
        """批量处理"""
        auth = await self._check_auth(request)
        if auth is None:
            return self._make_response(False, error="需要 API Key")

        try:
            data = await request.json()
        except json.JSONDecodeError:
            return self._make_response(False, error="无效的 JSON")

        texts = data.get('texts', [])
        operation = data.get('operation', 'query')

        results = []
        for text in texts:
            req = APIRequest(text=text, context=data.get('context'))
            try:
                if operation == 'summarize':
                    r = await self._do_summarize(req, self._generate_request_id())
                elif operation == 'polish':
                    r = await self._do_polish(req, self._generate_request_id())
                else:
                    r = await self._do_query(req, self._generate_request_id())
                results.append({"success": True, "data": r})
            except Exception as e:
                results.append({"success": False, "error": str(e)})

        return self._make_response(True, data={"results": results})

    async def _handle_health(self, request: web.Request) -> web.Response:
        """健康检查"""
        return web.json_response({
            "status": "healthy",
            "uptime_seconds": time.time() - self._start_time,
            "request_count": self._request_count,
        })

    async def _handle_capabilities(self, request: web.Request) -> web.Response:
        """能力列表"""
        return web.json_response({
            "capabilities": [
                {"id": "query", "name": "知识库查询", "description": "查询 AI OS 知识库"},
                {"id": "summarize", "name": "文档摘要", "description": "对长文本生成摘要"},
                {"id": "polish", "name": "文本润色", "description": "优化文本表达"},
                {"id": "translate", "name": "翻译", "description": "多语言翻译"},
                {"id": "correct", "name": "错别字纠正", "description": "检查并纠正错误"},
                {"id": "analyze", "name": "分析", "description": "深度分析文本"},
                {"id": "generate", "name": "内容生成", "description": "根据要求生成内容"},
            ],
            "supported_contexts": ["word", "wps", "excel", "outlook", "browser", "general"],
        })

    async def _handle_root(self, request: web.Request) -> web.Response:
        """根路径"""
        return web.json_response({
            "name": "AI OS External API",
            "version": "1.0.0",
            "docs": "/api/v1/capabilities",
        })

    # ============== 业务逻辑（需要接入 AI OS 核心） ==============

    async def _do_query(self, req: APIRequest, req_id: str) -> Dict[str, Any]:
        """执行查询"""
        # TODO: 接入 AI OS 知识库
        # if self.knowledge_base:
        #     return await self.knowledge_base.query(req.text)

        # 模拟响应
        return {
            "answer": f"[AI OS 知识库查询结果]\n\n您查询的: {req.text[:50]}...",
            "sources": ["knowledge_base"],
            "confidence": 0.95,
        }

    async def _do_summarize(self, req: APIRequest, req_id: str) -> Dict[str, Any]:
        """执行摘要"""
        # TODO: 接入 LLM
        return {
            "summary": f"[摘要] {req.text[:100]}...",
            "key_points": ["要点1", "要点2"],
            "word_count": len(req.text),
        }

    async def _do_polish(self, req: APIRequest, req_id: str) -> Dict[str, Any]:
        """执行润色"""
        return {
            "polished": f"[润色后] {req.text}",
            "changes": ["优化表达1", "优化表达2"],
        }

    async def _do_translate(self, req: APIRequest, req_id: str,
                            target_lang: str) -> Dict[str, Any]:
        """执行翻译"""
        return {
            "original": req.text,
            "translated": f"[翻译成 {target_lang}] {req.text}",
            "source_lang": "auto",
            "target_lang": target_lang,
        }

    async def _do_correct(self, req: APIRequest, req_id: str) -> Dict[str, Any]:
        """执行错别字纠正"""
        return {
            "corrected": req.text,
            "corrections": [],
        }

    async def _do_analyze(self, req: APIRequest, req_id: str) -> Dict[str, Any]:
        """执行分析"""
        return {
            "analysis": f"[分析结果] {req.text[:100]}...",
            "sentiment": "neutral",
            "entities": [],
        }

    async def _do_generate(self, req: APIRequest, req_id: str) -> Dict[str, Any]:
        """执行生成"""
        return {
            "generated": f"[生成内容]\n\n基于您的要求: {req.text}",
        }

    # ============== 启动 ==============

    def run(self):
        """同步启动"""
        web.run_app(self.app, host=self.host, port=self.port)

    async def start(self):
        """异步启动"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info(f"API 服务器启动: http://{self.host}:{self.port}")
        await asyncio.Event().wait()  # 永久运行


async def run_server(host: str = "127.0.0.1", port: int = 8898):
    """运行服务器"""
    server = ExternalAPIServer(host, port)
    await server.start()


# ============== 便捷客户端 ==============

class APIClient:
    """
    外部应用使用的 Python 客户端

    使用示例:
        client = APIClient()
        result = client.query("公司章程查询")
        result = client.summarize("长文本...")
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8898",
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self._session = None

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def _post(self, endpoint: str, data: Dict) -> Dict:
        """发送 POST 请求"""
        import aiohttp


        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                json=data,
                headers=self._get_headers(),
            ) as resp:
                result = await resp.json()
                if not result.get('success'):
                    raise Exception(result.get('error', 'Unknown error'))
                return result['data']

    def query(self, text: str, context: str = None) -> Dict:
        """查询"""
        return asyncio.run(self._post('/api/v1/query', {
            'text': text,
            'context': context,
        }))

    def summarize(self, text: str) -> Dict:
        """摘要"""
        return asyncio.run(self._post('/api/v1/summarize', {'text': text}))

    def polish(self, text: str) -> Dict:
        """润色"""
        return asyncio.run(self._post('/api/v1/polish', {'text': text}))

    def translate(self, text: str, target_lang: str = "en") -> Dict:
        """翻译"""
        return asyncio.run(self._post('/api/v1/translate', {
            'text': text,
            'options': {'target_lang': target_lang},
        }))

    def correct(self, text: str) -> Dict:
        """纠正"""
        return asyncio.run(self._post('/api/v1/correct', {'text': text}))

    def analyze(self, text: str) -> Dict:
        """分析"""
        return asyncio.run(self._post('/api/v1/analyze', {'text': text}))

    def generate(self, prompt: str) -> Dict:
        """生成"""
        return asyncio.run(self._post('/api/v1/generate', {'text': prompt}))
