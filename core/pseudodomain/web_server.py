"""
去中心化伪域名 - 微型 Web 服务器 (生命之树版本)
本地渲染伪域名内容

功能:
- 监听本地端口
- 路由生命之树域名请求到对应内容服务
- 渲染 HTML/Markdown/动态内容
- 模板支持
"""

import asyncio
import logging
import json
import time
from typing import Optional, Dict, Callable, Any
from dataclasses import dataclass, field
from urllib.parse import urlparse, parse_qs

from .models import (
    DomainType, ContentSource, TreeSuffix,
    WebContent, PseudoDomain
)

logger = logging.getLogger(__name__)


@dataclass
class HTTPRequest:
    """HTTP 请求"""
    method: str                 # GET/POST/PUT/DELETE
    path: str                   # 请求路径
    query: Dict[str, str]       # 查询参数
    headers: Dict[str, str]     # 请求头
    host: str                   # Host 头
    body: Optional[bytes] = None  # 请求体
    domain: str = ""            # 解析后的域名
    node_id: str = ""           # 节点 ID
    subdomain: str = ""         # 子域名/服务名


@dataclass
class HTTPResponse:
    """HTTP 响应"""
    status: int = 200           # 状态码
    status_text: str = "OK"
    headers: Dict[str, str] = field(default_factory=dict)
    content_type: str = "text/html"
    body: str = ""
    cookies: Dict[str, str] = field(default_factory=dict)

    def to_bytes(self) -> bytes:
        """转换为字节"""
        # 状态行
        lines = [f"HTTP/1.1 {self.status} {self.status_text}"]

        # 响应头
        self.headers["Content-Type"] = self.content_type
        self.headers["Content-Length"] = str(len(self.body.encode('utf-8')))
        self.headers["Cache-Control"] = "no-cache"

        for key, value in self.headers.items():
            lines.append(f"{key}: {value}")

        # Cookie
        for name, value in self.cookies.items():
            lines.append(f"Set-Cookie: {name}={value}")

        lines.append("")
        lines.append(self.body)

        return "\r\n".join(lines).encode('utf-8')


class RouteHandler:
    """路由处理器基类"""

    def __init__(self):
        self.routes: Dict[str, Callable] = {}

    def register(self, path: str, handler: Callable):
        """注册路由"""
        self.routes[path] = handler

    async def handle(self, request: HTTPRequest) -> HTTPResponse:
        """处理请求"""
        path = request.path

        # 精确匹配
        if path in self.routes:
            return await self.routes[path](request)

        # 前缀匹配
        for route_path, handler in self.routes.items():
            if path.startswith(route_path):
                return await handler(request)

        # 404
        return HTTPResponse(
            status=404,
            status_text="Not Found",
            body="<h1>404 Not Found</h1><p>The requested URL was not found on this server.</p>"
        )


class BlogHandler(RouteHandler):
    """博客处理器"""

    def __init__(self, content_service: Callable):
        super().__init__()
        self.content_service = content_service

    async def handle(self, request: HTTPRequest) -> HTTPResponse:
        """处理博客请求"""
        if request.path == "/" or request.path == "":
            return await self._render_index(request)
        elif request.path.startswith("/post/"):
            post_id = request.path[6:]
            return await self._render_post(request, post_id)
        elif request.path.startswith("/api/posts"):
            return await self._api_posts(request)
        else:
            return HTTPResponse(
                status=404,
                status_text="Not Found",
                body="<h1>404</h1><p>Post not found</p>"
            )

    async def _render_index(self, request: HTTPRequest) -> HTTPResponse:
        """渲染博客首页"""
        # 获取文章列表
        if self.content_service:
            posts = await self.content_service("blog", "list", {"node_id": request.node_id})
        else:
            posts = []

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{request.node_id}'s Blog - Living Tree AI</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: linear-gradient(135deg, #e8f5e9 0%, #f1f8e9 100%); }}
        h1 {{ color: #2E7D32; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        .post {{ background: white; padding: 20px; margin: 15px 0; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 4px solid #4CAF50; }}
        .post h2 {{ margin-top: 0; color: #1B5E20; }}
        .post-meta {{ color: #689F38; font-size: 12px; margin-bottom: 10px; }}
        .post-excerpt {{ color: #555; line-height: 1.6; }}
        .footer {{ text-align: center; color: #8BC34A; margin-top: 40px; padding-top: 20px; border-top: 1px solid #c8e6c9; }}
        .tree-icon {{ color: #4CAF50; }}
    </style>
</head>
<body>
    <h1>🌿 {request.node_id}'s Blog</h1>
    <div class="posts">
        {''.join([f'''
        <div class="post">
            <h2>🌱 {p.get("title", "Untitled")}</h2>
            <div class="post-meta">👤 {p.get("author", "Anonymous")} | 🕐 {p.get("date", "Unknown")}</div>
            <div class="post-excerpt">{p.get("excerpt", "")}</div>
        </div>''' for p in posts])}
    </div>
    <div class="footer">
        <p>🌳 Powered by Living Tree AI - 根系相连，智慧生长</p>
        <p>🌐 {request.host}</p>
    </div>
</body>
</html>
        """
        return HTTPResponse(
            status=200,
            body=html,
            content_type="text/html; charset=utf-8"
        )

    async def _render_post(self, request: HTTPRequest, post_id: str) -> HTTPResponse:
        """渲染文章"""
        if self.content_service:
            post = await self.content_service("blog", "get", {"node_id": request.node_id, "post_id": post_id})
        else:
            post = None

        if not post:
            return HTTPResponse(
                status=404,
                body="<h1>404 - Post Not Found</h1>"
            )

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{post.get("title", "Untitled")} - P2P Blog</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .post {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #2C3E50; margin-top: 0; }}
        .meta {{ color: #95A5A6; font-size: 14px; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid #eee; }}
        .content {{ line-height: 1.8; color: #333; }}
        .back-link {{ display: inline-block; margin-top: 20px; color: #4A90D9; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="post">
        <h1>{post.get("title", "Untitled")}</h1>
        <div class="meta">👤 {post.get("author", "Anonymous")} | 🕐 {post.get("date", "Unknown")} | 💬 {post.get("comments", 0)} 评论</div>
        <div class="content">
            {post.get("content", "")}
        </div>
        <a href="/" class="back-link">← 返回首页</a>
    </div>
</body>
</html>
        """
        return HTTPResponse(
            status=200,
            body=html,
            content_type="text/html; charset=utf-8"
        )

    async def _api_posts(self, request: HTTPRequest) -> HTTPResponse:
        """API: 获取文章列表"""
        if self.content_service:
            posts = await self.content_service("blog", "list", {"node_id": request.node_id})
        else:
            posts = []

        return HTTPResponse(
            status=200,
            body=json.dumps({"posts": posts}),
            content_type="application/json"
        )


class ForumHandler(RouteHandler):
    """论坛处理器"""

    def __init__(self, content_service: Callable):
        super().__init__()
        self.content_service = content_service

    async def handle(self, request: HTTPRequest) -> HTTPResponse:
        """处理论坛请求"""
        if request.path == "/" or request.path == "":
            return await self._render_index(request)
        elif request.path.startswith("/topic/"):
            topic_id = request.path[7:]
            return await self._render_topic(request, topic_id)
        elif request.path.startswith("/post/"):
            post_id = request.path[6:]
            return await self._render_post(request, post_id)
        else:
            return HTTPResponse(
                status=404,
                body="<h1>404</h1>"
            )

    async def _render_index(self, request: HTTPRequest) -> HTTPResponse:
        """渲染论坛首页"""
        if self.content_service:
            topics = await self.content_service("forum", "list_topics", {"node_id": request.node_id})
        else:
            topics = []

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>🌲 Forum - Living Tree AI</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: linear-gradient(135deg, #e8f5e9 0%, #f1f8e9 100%); }}
        h1 {{ color: #2E7D32; }}
        .topic {{ background: white; padding: 15px 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); cursor: pointer; border-left: 4px solid #4CAF50; }}
        .topic:hover {{ background: #f8f9fa; }}
        .topic-name {{ font-size: 16px; font-weight: 500; color: #1B5E20; }}
        .topic-meta {{ color: #689F38; font-size: 12px; margin-top: 5px; }}
    </style>
</head>
<body>
    <h1>🌲 生命之树论坛</h1>
    <div class="topics">
        {''.join([f'''
        <div class="topic" onclick="location.href='/topic/{t.get("id", "")}'">
            <div class="topic-name">{t.get("icon", "🌰")} {t.get("name", "Unnamed")}</div>
            <div class="topic-meta">🌿 {t.get("posts", 0)} 帖子 | 👥 {t.get("members", 0)} 成员</div>
        </div>''' for t in topics])}
    </div>
</body>
</html>
        """
        return HTTPResponse(status=200, body=html, content_type="text/html; charset=utf-8")

    async def _render_topic(self, request: HTTPRequest, topic_id: str) -> HTTPResponse:
        """渲染话题页面"""
        if self.content_service:
            posts = await self.content_service("forum", "topic_posts", {"node_id": request.node_id, "topic_id": topic_id})
        else:
            posts = []

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Topic - P2P Forum</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .post {{ background: white; padding: 20px; margin: 15px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .post-title {{ font-size: 18px; font-weight: 600; color: #2C3E50; margin-bottom: 10px; }}
        .post-meta {{ color: #95A5A6; font-size: 12px; margin-bottom: 10px; }}
        .post-content {{ line-height: 1.6; color: #333; }}
    </style>
</head>
<body>
    <h1>📋 Topic: {topic_id}</h1>
    <div class="posts">
        {''.join([f'''
        <div class="post">
            <div class="post-title">{p.get("title", "Untitled")}</div>
            <div class="post-meta">👤 {p.get("author", "Anonymous")} | 👍 {p.get("upvotes", 0)} | 💬 {p.get("replies", 0)}</div>
            <div class="post-content">{p.get("excerpt", "")}</div>
        </div>''' for p in posts])}
    </div>
</body>
</html>
        """
        return HTTPResponse(status=200, body=html, content_type="text/html; charset=utf-8")

    async def _render_post(self, request: HTTPRequest, post_id: str) -> HTTPResponse:
        """渲染帖子页面"""
        return HTTPResponse(status=200, body=f"<h1>Post: {post_id}</h1><p>Coming soon...</p>")


class StaticHandler(RouteHandler):
    """静态文件处理器"""

    def __init__(self):
        super().__init__()
        self._setup_default_routes()

    def _setup_default_routes(self):
        """设置默认路由"""
        self.register("/favicon.ico", self._favicon)

    async def _favicon(self, request: HTTPRequest) -> HTTPResponse:
        """favicon"""
        return HTTPResponse(
            status=200,
            body="",
            content_type="image/x-icon"
        )

    async def handle(self, request: HTTPRequest) -> HTTPResponse:
        """处理静态文件"""
        path = request.path

        if path in self.routes:
            return await self.routes[path](request)

        # 404
        return HTTPResponse(
            status=404,
            body="<h1>404 Not Found</h1>"
        )


class WebServer:
    """
    微型 Web 服务器

    监听本地端口, 路由伪域名请求
    """

    def __init__(self, port: int = 8080):
        self.port = port
        self._server = None
        self._running = False

        # 路由处理器
        self._handlers: Dict[str, RouteHandler] = {}

        # 内容服务回调
        self._content_callback: Optional[Callable] = None

        # 默认处理器
        self._default_handler = RouteHandler()

    def set_content_callback(self, callback: Callable):
        """设置内容服务回调"""
        self._content_callback = callback
        # 重新初始化处理器
        self._init_handlers()

    def _init_handlers(self):
        """初始化处理器"""
        # 博客
        self._handlers["blog"] = BlogHandler(self._content_callback)
        # 论坛
        self._handlers["forum"] = ForumHandler(self._content_callback)
        # 静态
        self._handlers["static"] = StaticHandler()

    async def handle_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理请求"""
        try:
            # 读取请求
            data = await reader.read(65536)
            if not data:
                return

            # 解析请求
            request = self._parse_request(data)
            if not request:
                return

            # 确定处理器
            handler = self._default_handler
            if request.subdomain in self._handlers:
                handler = self._handlers[request.subdomain]
            elif request.host:
                # 从 host 提取 subdomain
                host_parts = request.host.split('.')
                if host_parts[0] in self._handlers:
                    handler = self._handlers[host_parts[0]]

            # 处理请求
            response = await handler.handle(request)

            # 发送响应
            writer.write(response.to_bytes())
            await writer.drain()

        except Exception as e:
            logger.error(f"Request handling error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    def _parse_request(self, data: bytes) -> Optional[HTTPRequest]:
        """解析 HTTP 请求"""
        try:
            lines = data.decode('utf-8', errors='ignore').split('\r\n')
            if not lines:
                return None

            # 请求行
            request_line = lines[0].split(' ')
            if len(request_line) < 2:
                return None

            method = request_line[0]
            path = request_line[1]

            # 解析路径
            parsed = urlparse(path)
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}

            # 请求头
            headers = {}
            for line in lines[1:]:
                if line == "":
                    break
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip()] = value.strip()

            # Host
            host = headers.get("Host", "")

            # 解析域名
            from .models import parse_pseudo_domain
            domain_type, node_id, subdomain, tree_suffix = parse_pseudo_domain(host)

            return HTTPRequest(
                method=method,
                path=parsed.path,
                query=query,
                headers=headers,
                host=host,
                body=None,
                domain=host,
                node_id=node_id or "",
                subdomain=subdomain or ""
            )

        except Exception as e:
            logger.error(f"Parse request error: {e}")
            return None

    async def start(self):
        """启动服务器"""
        self._init_handlers()
        self._server = await asyncio.start_server(
            self.handle_request,
            '127.0.0.1',
            self.port
        )
        self._running = True
        logger.info(f"Web server started on http://127.0.0.1:{self.port}")

    async def stop(self):
        """停止服务器"""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("Web server stopped")

    def is_running(self) -> bool:
        """检查是否运行中"""
        return self._running


def create_default_server(port: int = 8080) -> WebServer:
    """创建默认 Web 服务器"""
    return WebServer(port=port)
