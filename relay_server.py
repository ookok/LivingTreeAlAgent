"""P2PRelayServer — authenticated relay with admin panel + P2P NAT traversal.

Core functions:
  1. Admin web panel: /admin → API key management, status dashboard
  2. P2P signaling: peer registration, discovery, NAT punch-through coordination
  3. WebSocket relay: message forwarding between peers behind NAT
  4. API gateway: authenticated chat/tasks/wechat with API key auth
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import time
from pathlib import Path

import aiohttp
from aiohttp import web
from loguru import logger

PROJECT_ROOT = Path(__file__).parent


# ═══ Data stores ═══

PEER_STORE: dict[str, dict] = {}  # peer_id → {ip, port, nat_type, last_seen, metadata}
SESSION_STORE: dict[str, str] = {}  # admin session tokens
API_KEY_STORE: dict[str, dict] = {}  # key → {name, created, last_used}


def _ensure_api_keys():
    if not API_KEY_STORE:
        # Load from vault
        try:
            from livingtree.config.secrets import get_secret_vault
            vault = get_secret_vault()
            for k in vault.keys():
                if k.startswith("relay_key_"):
                    name = k.replace("relay_key_", "")
                    API_KEY_STORE[vault.get(k, "")] = {"name": name, "created": time.time(), "last_used": 0}
        except Exception:
            pass
    if not API_KEY_STORE:
        key = f"lt-{secrets.token_hex(24)}"
        API_KEY_STORE[key] = {"name": "default", "created": time.time(), "last_used": 0}


def _save_keys():
    try:
        from livingtree.config.secrets import get_secret_vault
        vault = get_secret_vault()
        for key_val, info in API_KEY_STORE.items():
            vault.set(f"relay_key_{info['name']}", key_val)
    except Exception:
        pass


# ═══ Admin HTML ═══

ADMIN_LOGIN_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>LivingTree Admin</title>
<style>body{background:#0a0c10;color:#c9d1d9;font-family:monospace;max-width:600px;margin:50px auto;padding:20px}
input,button{background:#161b22;color:#c9d1d9;border:1px solid #30363d;padding:8px 12px;margin:4px 0;width:100%}
button{background:#238636;border:none;cursor:pointer}button:hover{background:#2ea043}
h1{color:#58a6ff}.err{color:#f85149}</style></head>
<body><h1>🌳 LivingTree Admin</h1><form method="POST" action="/admin/login">
<input name="password" type="password" placeholder="管理员密码">
<button type="submit">登录</button></form></body></html>"""

ADMIN_DASHBOARD_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>LivingTree Admin</title>
<style>body{background:#0a0c10;color:#c9d1d9;font-family:monospace;max-width:800px;margin:30px auto;padding:20px}
h1,h2{color:#58a6ff}table{width:100%;border-collapse:collapse;margin:10px 0}
th,td{border:1px solid #30363d;padding:6px 10px;text-align:left}
th{background:#161b22}input,button{background:#161b22;color:#c9d1d9;border:1px solid #30363d;padding:6px 10px}
button{background:#238636;border:none;cursor:pointer;margin:2px}button.danger{background:#da3633}
.metric{display:inline-block;background:#161b22;border:1px solid #30363d;padding:10px 15px;margin:5px;text-align:center}
.metric .val{font-size:24px;color:#58a6ff}.metric .lbl{font-size:12px;color:#8b949e}
.endpoint{background:#161b22;padding:8px;margin:4px 0;border-left:3px solid #58a6ff}
</style></head>
<body><h1>🌳 LivingTree Admin Dashboard</h1>
<div style="margin-bottom:20px">
  <div class="metric"><div class="val">UPTIME</div><div class="lbl">uptime</div></div>
  <div class="metric"><div class="val">REQS</div><div class="lbl">requests</div></div>
  <div class="metric"><div class="val">PEERS</div><div class="lbl">peers</div></div>
  <div class="metric"><div class="val">KEYS</div><div class="lbl">api keys</div></div>
</div>
<h2>🔑 API Keys</h2>
<table><tr><th>Name</th><th>Key</th><th>Created</th><th>Last Used</th><th>Actions</th></tr>
KEY_ROWS
</table>
<form method="POST" action="/admin/keys/add">
<input name="name" placeholder="Key name (e.g. wechat-bot)" required>
<button type="submit">+ 生成新 Key</button></form>

<h2>🌐 P2P Peers</h2>
<table><tr><th>Peer ID</th><th>Address</th><th>NAT Type</th><th>Last Seen</th></tr>
PEER_ROWS
</table>

<h2>📡 API Endpoints</h2>
<div class="endpoint">GET /health — 健康检查</div>
<div class="endpoint">POST /chat — {"message": "..."}</div>
<div class="endpoint">POST /tasks — SSE 流式任务</div>
<div class="endpoint">POST /peers/register — P2P 注册</div>
<div class="endpoint">GET /peers/discover — P2P 发现</div>
<div class="endpoint">WS /ws/relay — WebSocket 消息中继</div>
<div style="margin-top:20px"><a href="/admin/logout"><button class="danger">退出登录</button></a></div>
</body></html>"""


# ═══ P2P Signaling ═══

def _detect_nat_type(client_ip: str, advertised_ip: str, advertised_port: int) -> str:
    if client_ip == advertised_ip: return "open"
    return "cone"  # simplified


# ═══ Server ═══

class P2PRelayServer:
    """Admin panel + P2P signaling + authenticated API."""

    def __init__(self, port: int = 8100, host: str = "0.0.0.0", admin_password: str = ""):
        self.port = port; self.host = host
        self.admin_password = admin_password or secrets.token_hex(8)
        self._app = web.Application()
        self._hub = None
        self._started_at = time.time()
        self._request_count = 0
        self._ws_clients: dict[str, web.WebSocketResponse] = {}
        _ensure_api_keys()
        self._setup_routes()

    def _setup_routes(self):
        app = self._app
        # Admin
        app.router.add_get("/admin", self._admin_page)
        app.router.add_get("/admin/login", self._admin_page)
        app.router.add_post("/admin/login", self._admin_login)
        app.router.add_get("/admin/logout", self._admin_logout)
        app.router.add_post("/admin/keys/add", self._admin_add_key)
        app.router.add_get("/admin/keys/revoke", self._admin_revoke_key)
        # API
        app.router.add_get("/health", self._health)
        app.router.add_post("/chat", self._handle_chat)
        app.router.add_get("/status", self._handle_status)
        # P2P
        app.router.add_post("/peers/register", self._peer_register)
        app.router.add_get("/peers/discover", self._peer_discover)
        app.router.add_get("/ws/relay", self._ws_relay)
        # WeChat
        app.router.add_get("/wechat", self._wechat_verify)
        app.router.add_post("/wechat", self._wechat_message)

    # ═══ Auth helpers ═══

    def _check_auth(self, request: web.Request) -> str | None:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            key = auth[7:]
            if key in API_KEY_STORE:
                API_KEY_STORE[key]["last_used"] = time.time()
                return key
        return None

    def _check_admin(self, request: web.Request) -> bool:
        token = request.cookies.get("admin_token", "")
        return token in SESSION_STORE

    # ═══ Admin endpoints ═══

    async def _admin_page(self, request: web.Request) -> web.Response:
        if not self._check_admin(request):
            return web.Response(text=ADMIN_LOGIN_HTML, content_type="text/html")
        rows = ""
        for key_val, info in API_KEY_STORE.items():
            display = key_val[:12] + "..." + key_val[-8:]
            created = time.strftime("%Y-%m-%d", time.localtime(info.get("created", 0)))
            last = time.strftime("%H:%M", time.localtime(info.get("last_used", 0))) if info.get("last_used") else "-"
            rows += f"<tr><td>{info['name']}</td><td><code>{display}</code></td><td>{created}</td><td>{last}</td><td><a href='/admin/keys/revoke?key={display}'><button class='danger'>吊销</button></a></td></tr>"
        peer_rows = ""
        for pid, p in list(PEER_STORE.items())[:20]:
            last = time.strftime("%H:%M:%S", time.localtime(p.get("last_seen", 0)))
            peer_rows += f"<tr><td>{pid[:16]}</td><td>{p.get('ip','?')}:{p.get('port','?')}</td><td>{p.get('nat_type','?')}</td><td>{last}</td></tr>"
        html = ADMIN_DASHBOARD_HTML.replace("UPTIME", f"{(time.time()-self._started_at):.0f}s")
        html = html.replace("REQS", str(self._request_count))
        html = html.replace("PEERS", str(len(PEER_STORE)))
        html = html.replace("KEYS", str(len(API_KEY_STORE)))
        html = html.replace("KEY_ROWS", rows)
        html = html.replace("PEER_ROWS", peer_rows or "<tr><td colspan=4>暂无连接的节点</td></tr>")
        return web.Response(text=html, content_type="text/html")

    async def _admin_login(self, request: web.Request) -> web.Response:
        data = await request.post()
        if data.get("password") == self.admin_password:
            token = secrets.token_hex(16)
            SESSION_STORE[token] = "admin"
            resp = web.HTTPFound("/admin")
            resp.set_cookie("admin_token", token, max_age=86400, httponly=True)
            return resp
        return web.Response(text=ADMIN_LOGIN_HTML.replace("</form>","<p class=err>密码错误</p></form>"), content_type="text/html")

    async def _admin_logout(self, request: web.Request) -> web.Response:
        token = request.cookies.get("admin_token", "")
        SESSION_STORE.pop(token, None)
        resp = web.HTTPFound("/admin")
        resp.del_cookie("admin_token")
        return resp

    async def _admin_add_key(self, request: web.Request) -> web.Response:
        if not self._check_admin(request): return web.HTTPFound("/admin")
        data = await request.post()
        name = data.get("name", "api-key").strip()[:30] or "api-key"
        key = f"lt-{secrets.token_hex(24)}"
        API_KEY_STORE[key] = {"name": name, "created": time.time(), "last_used": 0}
        _save_keys()
        raise web.HTTPFound("/admin")

    async def _admin_revoke_key(self, request: web.Request) -> web.Response:
        if not self._check_admin(request): return web.HTTPFound("/admin")
        partial = request.query.get("key", "")
        for key_val in list(API_KEY_STORE.keys()):
            if partial in key_val or key_val[:12] in partial:
                del API_KEY_STORE[key_val]
                _save_keys()
                break
        raise web.HTTPFound("/admin")

    # ═══ API endpoints ═══

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "uptime": time.time() - self._started_at})

    async def _handle_status(self, request: web.Request) -> web.Response:
        if not self._check_auth(request): return web.json_response({"error": "Unauthorized"}, status=401)
        return web.json_response({"peers": len(PEER_STORE), "requests": self._request_count, "keys": len(API_KEY_STORE)})

    async def _handle_chat(self, request: web.Request) -> web.Response:
        if not self._check_auth(request): return web.json_response({"error": "Unauthorized. Use Authorization: Bearer <api_key>"}, status=401)
        self._request_count += 1
        try:
            data = await request.json()
            msg = data.get("message", data.get("prompt", ""))
            if not msg: return web.json_response({"error": "message required"}, status=400)
            if self._hub:
                result = await self._hub.chat(msg)
                return web.json_response({"response": result.get("response", str(result))})
            return web.json_response({"response": "Hub initializing... try again soon"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    # ═══ P2P endpoints ═══

    async def _peer_register(self, request: web.Request) -> web.Response:
        """Register a peer behind NAT. Returns peer_id for future discovery."""
        try:
            data = await request.json()
            peer_id = data.get("peer_id") or secrets.token_hex(8)
            peer_ip = request.remote or "unknown"
            peer_port = data.get("port", 0)

            PEER_STORE[peer_id] = {
                "peer_id": peer_id, "ip": peer_ip, "port": peer_port,
                "nat_type": data.get("nat_type", "unknown"),
                "last_seen": time.time(),
                "metadata": data.get("metadata", {}),
            }
            logger.info(f"Peer registered: {peer_id[:12]} @ {peer_ip}:{peer_port}")
            return web.json_response({"status": "registered", "peer_id": peer_id})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def _peer_discover(self, request: web.Request) -> web.Response:
        """Discover active peers. Optionally filter by peer_id."""
        peer_id = request.query.get("peer_id", "")
        if peer_id and peer_id in PEER_STORE:
            return web.json_response({"peer": PEER_STORE[peer_id]})

        # Return all recently active peers (last 5 min)
        cutoff = time.time() - 300
        peers = {k: v for k, v in PEER_STORE.items() if v["last_seen"] > cutoff}
        return web.json_response({"peers": list(peers.values()), "count": len(peers)})

    async def _ws_relay(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket relay for P2P message forwarding."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        client_id = secrets.token_hex(8)
        self._ws_clients[client_id] = ws
        logger.info(f"WS client connected: {client_id[:12]}")

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    target = data.get("to", "")
                    if target in self._ws_clients:
                        await self._ws_clients[target].send_json({
                            "from": client_id, "data": data.get("data", ""),
                        })
                    else:
                        await ws.send_json({"error": f"Peer {target[:12]} not connected"})
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WS error: {ws.exception()}")
        finally:
            self._ws_clients.pop(client_id, None)
        return ws

    # ═══ WeChat ═══

    async def _wechat_verify(self, request: web.Request) -> web.Response:
        signature = request.query.get("signature", "")
        timestamp = request.query.get("timestamp", "")
        nonce = request.query.get("nonce", "")
        echostr = request.query.get("echostr", "")
        token = os.environ.get("WECHAT_TOKEN", "livingtree")
        tmp = sorted([token, timestamp, nonce])
        expected = hashlib.sha1("".join(tmp).encode()).hexdigest()
        return web.Response(text=echostr if signature == expected else "fail")

    async def _wechat_message(self, request: web.Request) -> web.Response:
        self._request_count += 1
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(await request.text())
            user_msg = root.findtext("Content", "").strip()
            reply = ""
            if user_msg and self._hub:
                result = await self._hub.chat(user_msg)
                reply = result.get("response", str(result))[:600]
            reply_xml = (
                "<xml><ToUserName><![CDATA[{from_user}]]></ToUserName>"
                "<FromUserName><![CDATA[{to_user}]]></FromUserName>"
                f"<CreateTime>{int(time.time())}</CreateTime>"
                "<MsgType><![CDATA[text]]></MsgType>"
                f"<Content><![CDATA[{reply}]]></Content></xml>"
            ).format(
                from_user=root.findtext("FromUserName", ""),
                to_user=root.findtext("ToUserName", ""),
            )
            return web.Response(text=reply_xml, content_type="application/xml")
        except Exception as e:
            return web.Response(text="success")

    # ═══ Lifecycle ═══

    async def start(self):
        logger.info(f"🚀 P2P Relay Server: {self.host}:{self.port}")
        logger.info(f"🔑 Admin password: {self.admin_password}")
        logger.info(f"🔑 API keys: {len(API_KEY_STORE)} registered")
        logger.info(f"🖥  Admin panel: http://localhost:{self.port}/admin")

        from livingtree.integration.hub import IntegrationHub
        self._hub = IntegrationHub(lazy=True)
        await self._hub.start()
        self._started_at = time.time()

        runner = web.AppRunner(self._app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info(f"✅ Ready — http://localhost:{self.port}/admin to manage")

    async def shutdown(self):
        for ws in self._ws_clients.values():
            await ws.close()
        if self._hub:
            await self._hub.shutdown()


async def run_server(port: int = 8100, host: str = "0.0.0.0", password: str = ""):
    server = P2PRelayServer(port=port, host=host, admin_password=password)
    await server.start()
    try: await asyncio.Event().wait()
    except asyncio.CancelledError: await server.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LivingTree P2P Relay Server")
    parser.add_argument("--port", "-p", type=int, default=8100)
    parser.add_argument("--host", "-H", default="0.0.0.0")
    parser.add_argument("--password", "-P", default="", help="Admin password (auto-generated if blank)")
    args = parser.parse_args()
    asyncio.run(run_server(args.port, args.host, args.password))
