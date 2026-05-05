"""P2PRelayServer — account auth + admin panel + P2P signaling + cost tracking.

Relay address: www.mogoo.com.cn:8888 (hardcoded)

Core functions:
  1. Client login: account/password required, no self-registration
  2. Admin panel: /admin → account CRUD, password reset, per-node cost dashboard
  3. P2P signaling: peer registration, discovery, WebSocket relay
  4. Token cost tracking: per-account, RMB-converted

Deployment:
  Standalone exe: python build_relay_exe.py → dist/relay_server.exe
  Win2008: deploy_win2008.bat <target> → bundles exe + CRT DLLs
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import secrets
import sys
import time
from pathlib import Path

import aiohttp
from aiohttp import web
from loguru import logger

# ═══ Win2008 compatibility: prefer SelectorEventLoop ═══
_WIN_VER = getattr(sys, 'getwindowsversion', lambda: None)()
if _WIN_VER and hasattr(_WIN_VER, 'major') and _WIN_VER.major < 10:
    try:
        loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(loop)
        logger.info("Win2008: SelectorEventLoop set")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).parent

# ═══ Data stores ═══
PEER_STORE: dict[str, dict] = {}
ACCOUNT_STORE: dict[str, dict] = {}  # username → {password_hash, created, cost_rmb, token_in, token_out, last_login}
SESSION_STORE: dict[str, str] = {}
API_KEY_STORE: dict[str, dict] = {}

RELAY_HOST = "www.mogoo.com.cn"
RELAY_PORT = 8888

# ═══ Load balance pool (P2P only) ═══
RELAY_POOL: list[str] = []  # ["host:port", ...]
RELAY_POOL_FILE = Path(".livingtree/relay_pool.json")

# RMB per 1M tokens (approximate)
RMB_PER_M_TOKENS = {
    "deepseek": 2.0, "siliconflow": 0.0, "mofang": 0.0,
    "longcat": 0.0, "zhipu": 0.0, "spark": 0.0,
    "xiaomi": 8.0, "aliyun": 4.0, "dmxapi": 3.5,
    "opencode-serve": 0.0, "default": 4.0,
}


def _ensure_accounts():
    if not ACCOUNT_STORE:
        try:
            path = Path(".livingtree/relay_accounts.json")
            if path.exists():
                for name, data in json.loads(path.read_text()).items():
                    ACCOUNT_STORE[name] = data
        except Exception:
            pass
    if not ACCOUNT_STORE:
        ACCOUNT_STORE["admin"] = {
            "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
            "created": time.time(), "cost_rmb": 0.0, "token_in": 0, "token_out": 0,
            "last_login": 0, "is_admin": True,
        }

def _save_accounts():
    try:
        path = Path(".livingtree/relay_accounts.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(ACCOUNT_STORE, indent=2, ensure_ascii=False))
    except Exception:
        pass

def _hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _load_relay_pool():
    global RELAY_POOL
    try:
        if RELAY_POOL_FILE.exists():
            RELAY_POOL = json.loads(RELAY_POOL_FILE.read_text())
    except Exception:
        RELAY_POOL = []

def _save_relay_pool():
    try:
        RELAY_POOL_FILE.parent.mkdir(parents=True, exist_ok=True)
        RELAY_POOL_FILE.write_text(json.dumps(RELAY_POOL))
    except Exception: pass

def _ensure_api_keys():
    if not API_KEY_STORE:
        try:
            from livingtree.config.secrets import get_secret_vault
            vault = get_secret_vault()
            for k in vault.keys():
                if k.startswith("relay_key_"):
                    name = k.replace("relay_key_", "")
                    API_KEY_STORE[vault.get(k, "")] = {"name": name, "created": time.time(), "last_used": 0}
        except Exception: pass
    if not API_KEY_STORE:
        key = f"lt-{secrets.token_hex(24)}"
        API_KEY_STORE[key] = {"name": "default", "created": time.time(), "last_used": 0}


# ═══ Admin HTML ═══

ADMIN_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LivingTree Admin</title>
<style>
*{box-sizing:border-box}body{background:#0a0c10;color:#c9d1d9;font-family:monospace;max-width:900px;margin:20px auto;padding:15px}
h1,h2{color:#58a6ff}h2{border-bottom:1px solid #30363d;padding-bottom:5px}
table{width:100%;border-collapse:collapse;margin:8px 0;font-size:13px}
th,td{border:1px solid #30363d;padding:5px 8px;text-align:left}
th{background:#161b22;color:#58a6ff}
input,button{background:#161b22;color:#c9d1d9;border:1px solid #30363d;padding:6px 10px;margin:3px 0;font-family:monospace}
button{background:#238636;border:none;cursor:pointer}button:hover{background:#2ea043}
button.danger{background:#da3633}button.small{padding:3px 8px;font-size:12px}
.metric{display:inline-block;background:#161b22;border:1px solid #30363d;padding:8px 14px;margin:4px;text-align:center;min-width:90px}
.metric .val{font-size:22px;color:#58a6ff}.metric .lbl{font-size:11px;color:#8b949e}
.row{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.card{background:#161b22;border:1px solid #30363d;padding:12px;flex:1;min-width:200px}
.endpoint{background:#161b22;padding:6px 10px;margin:3px 0;border-left:3px solid #58a6ff;font-size:12px}
.add-form{display:flex;gap:6px}.add-form input{flex:1}
</style></head>
<body>
<h1>🌳 LivingTree Admin</h1>
<div class="row">
  <div class="metric"><div class="val">UPTIME</div><div class="lbl">运行时间(s)</div></div>
  <div class="metric"><div class="val">REQS</div><div class="lbl">总请求</div></div>
  <div class="metric"><div class="val">PEERS</div><div class="lbl">在线节点</div></div>
  <div class="metric"><div class="val">ACCTS</div><div class="lbl">账户数</div></div>
  <div class="metric"><div class="val">¥COST</div><div class="lbl">累计费用</div></div>
</div>

<h2>👤 账户管理</h2>
<form class="add-form" method="POST" action="/admin/accounts/add">
  <input name="username" placeholder="用户名" required>
  <input name="password" placeholder="密码" required>
  <button type="submit">+ 添加</button>
</form>
<table><tr><th>用户名</th><th>创建时间</th><th>Token输入</th><th>Token输出</th><th>累计费用(¥)</th><th>最后登录</th><th>操作</th></tr>
ACCOUNT_ROWS</table>

<h2>💰 费用明细</h2>
<table><tr><th>用户名</th><th>Provider</th><th>Token输入</th><th>Token输出</th><th>单价(¥/M)</th><th>费用(¥)</th></tr>
COST_ROWS</table>

<h2>🔄 负载均衡 (P2P)</h2>
<form method="POST" action="/admin/relays/add"><input name="address" placeholder="host:port" required style="width:70%"><button type="submit">+ 添加</button></form>
<table><tr><th>地址</th><th>操作</th></tr>
RELAY_ROWS</table>

<h2>🌐 P2P节点</h2>
<table><tr><th>节点ID</th><th>地址</th><th>位置</th><th>最后心跳</th><th>Token消耗(¥)</th></tr>
PEER_ROWS</table>

<h2>🔑 API Keys</h2>
<table><tr><th>名称</th><th>Key</th><th>创建</th><th>操作</th></tr>
KEY_ROWS</table>
<form method="POST" action="/admin/keys/add"><input name="name" placeholder="Key名称" required><button type="submit">+ 生成</button></form>

<h2>📡 API端点</h2>
<div class="endpoint">POST /login — {"username":"","password":""} → {"token":"..."}</div>
<div class="endpoint">POST /chat — Authorization: Bearer &lt;token&gt; {"message":"..."}</div>
<div class="endpoint">POST /peers/register — P2P节点注册</div>
<div class="endpoint">GET /peers/discover — P2P节点发现</div>
<div class="endpoint">WS /ws/relay — WebSocket消息中继</div>
<div class="endpoint">POST /cost/report — 上报token消耗</div>
<div style="margin-top:15px">
<a href="/admin/stats/reset?scope=costs"><button class="danger">🗑 清空费用统计</button></a>
<a href="/admin/stats/reset?scope=peers"><button class="danger">🗑 清空节点列表</button></a>
<a href="/admin/stats/reset?scope=all"><button class="danger">🗑 清空全部统计</button></a>
<a href="/admin/logout" style="margin-left:20px"><button>退出登录</button></a>
</div>
</body></html>"""

LOGIN_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>LivingTree Login</title>
<style>body{background:#0a0c10;color:#c9d1d9;font-family:monospace;max-width:400px;margin:80px auto;padding:20px}
input,button{background:#161b22;color:#c9d1d9;border:1px solid #30363d;padding:8px 12px;width:100%}
button{background:#238636;border:none;cursor:pointer;margin-top:8px}
h1{color:#58a6ff;text-align:center}.err{color:#f85149;margin:8px 0}</style></head>
<body><h1>🌳 LivingTree</h1>
<form method="POST" action="/admin/login">
<input name="username" placeholder="用户名" required>
<input name="password" type="password" placeholder="密码" required>
<button type="submit">登录</button>
ERR_MSG</form></body></html>"""


class P2PRelayServer:
    """Relay server with account auth + admin panel + cost tracking."""

    def __init__(self, port: int = 8888, host: str = "0.0.0.0"):
        self.port = port; self.host = host
        self._app = web.Application()
        self._hub = None
        self._started_at = time.time()
        self._request_count = 0
        self._ws_clients: dict[str, web.WebSocketResponse] = {}
        _ensure_accounts()
        _ensure_api_keys()
        _load_relay_pool()
        self._setup_routes()

    def _setup_routes(self):
        app = self._app
        # Client auth
        app.router.add_post("/login", self._login)
        # Admin
        app.router.add_get("/admin", self._admin_page)
        app.router.add_get("/admin/login", self._admin_login_page)
        app.router.add_post("/admin/login", self._admin_login)
        app.router.add_get("/admin/logout", self._admin_logout)
        app.router.add_post("/admin/accounts/add", self._admin_add_account)
        app.router.add_get("/admin/accounts/reset", self._admin_reset_password)
        app.router.add_get("/admin/accounts/delete", self._admin_delete_account)
        app.router.add_get("/admin/stats/reset", self._admin_reset_stats)
        app.router.add_post("/admin/relays/add", self._admin_add_relay)
        app.router.add_get("/admin/relays/remove", self._admin_remove_relay)
        app.router.add_post("/admin/keys/add", self._admin_add_key)
        app.router.add_get("/admin/keys/revoke", self._admin_revoke_key)
        # API
        app.router.add_get("/health", self._health)
        app.router.add_post("/chat", self._handle_chat)
        app.router.add_get("/status", self._handle_status)
        app.router.add_post("/cost/report", self._cost_report)
        # P2P
        app.router.add_post("/peers/register", self._peer_register)
        app.router.add_get("/peers/discover", self._peer_discover)
        app.router.add_get("/ws/relay", self._ws_relay)
        # WeChat
        app.router.add_get("/wechat", self._wechat_verify)
        app.router.add_post("/wechat", self._wechat_message)

    # ═══ Auth ═══

    def _check_auth(self, request: web.Request) -> str | None:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            # Token format: username:session_token
            for username, data in ACCOUNT_STORE.items():
                expected = hashlib.sha256(f"{username}:{data.get('password_hash','')}".encode()).hexdigest()[:32]
                if token == expected or token == data.get("session_token", ""):
                    return username
            # Check API keys
            if token in API_KEY_STORE:
                return "api"
        return None

    def _check_admin(self, request: web.Request) -> bool:
        token = request.cookies.get("admin_token", "")
        return token in SESSION_STORE

    # ═══ Client login ═══

    async def _login(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            username = data.get("username", "").strip()
            password = data.get("password", "")
            if not username or not password:
                return web.json_response({"error": "username and password required"}, status=400)
            account = ACCOUNT_STORE.get(username)
            if not account:
                return web.json_response({"error": "账户不存在"}, status=401)
            if account["password_hash"] != _hash_password(password):
                return web.json_response({"error": "密码错误"}, status=401)
            # Generate session token
            token = hashlib.sha256(f"{username}:{account['password_hash']}".encode()).hexdigest()[:32]
            account["session_token"] = token
            account["last_login"] = time.time()
            _save_accounts()
            return web.json_response({"token": token, "username": username, "node_id": f"lt-{username}"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    # ═══ Admin pages ═══

    async def _admin_login_page(self, request: web.Request) -> web.Response:
        return web.Response(text=LOGIN_HTML.replace("ERR_MSG", ""), content_type="text/html")

    async def _admin_page(self, request: web.Request) -> web.Response:
        if not self._check_admin(request):
            return web.Response(text=LOGIN_HTML.replace("ERR_MSG", ""), content_type="text/html")

        # Account rows
        account_rows = ""
        for name, a in ACCOUNT_STORE.items():
            created = time.strftime("%m-%d %H:%M", time.localtime(a.get("created", 0)))
            last = time.strftime("%m-%d %H:%M", time.localtime(a.get("last_login", 0))) if a.get("last_login") else "-"
            reset_link = f"/admin/accounts/reset?user={name}"
            del_link = f"/admin/accounts/delete?user={name}"
            account_rows += f"<tr><td>{name}{' [管理员]' if a.get('is_admin') else ''}</td><td>{created}</td><td>{a.get('token_in',0):,}</td><td>{a.get('token_out',0):,}</td><td>¥{a.get('cost_rmb',0):.4f}</td><td>{last}</td><td><a href='{reset_link}'><button class='small'>改密</button></a> <a href='{del_link}' onclick='return confirm(\"删除{name}?\")'><button class='small danger'>删除</button></a></td></tr>"

        # Cost rows (per-account per-provider)
        cost_rows = ""
        total_cost = 0.0
        for name, a in ACCOUNT_STORE.items():
            cost_breakdown = a.get("cost_breakdown", {})
            for provider, cost_data in cost_breakdown.items():
                cost_rows += f"<tr><td>{name}</td><td>{provider}</td><td>{cost_data.get('in',0):,}</td><td>{cost_data.get('out',0):,}</td><td>¥{RMB_PER_M_TOKENS.get(provider,4.0)}/M</td><td>¥{cost_data.get('cost',0):.4f}</td></tr>"
            total_cost += a.get("cost_rmb", 0)

        # Peer rows with cost
        peer_rows = ""
        for pid, p in list(PEER_STORE.items())[:20]:
            last = time.strftime("%H:%M:%S", time.localtime(p.get("last_seen", 0)))
            username = p.get("metadata", {}).get("username", "")
            acct = ACCOUNT_STORE.get(username, {})
            cost = acct.get("cost_rmb", 0)
            loc = p.get("metadata", {}).get("location", {})
            loc_str = f"{loc.get('city','')} {loc.get('region','')} {loc.get('country','')}".strip() or "未知"
            peer_rows += f"<tr><td>{pid[:16]}...</td><td>{p.get('ip','?')}:{p.get('port','?')}</td><td>{loc_str}</td><td>{last}</td><td>¥{cost:.4f}</td></tr>"

        # Relay pool rows
        all_relays = [f"{RELAY_HOST}:{RELAY_PORT}"] + RELAY_POOL
        relay_rows = ""
        for addr in all_relays:
            is_primary = addr == f"{RELAY_HOST}:{RELAY_PORT}"
            label = f"{addr} [主]" if is_primary else addr
            remove_link = f"/admin/relays/remove?addr={addr}" if not is_primary else ""
            action = f"<a href='{remove_link}'><button class='small danger'>移除</button></a>" if remove_link else "主服务器"
            relay_rows += f"<tr><td>{label}</td><td>{action}</td></tr>"

        # Key rows
        key_rows = ""
        for key_val, info in API_KEY_STORE.items():
            display = key_val[:12] + "..." + key_val[-8:]
            created = time.strftime("%m-%d", time.localtime(info.get("created", 0)))
            key_rows += f"<tr><td>{info['name']}</td><td><code>{display}</code></td><td>{created}</td><td><a href='/admin/keys/revoke?key={display}'><button class='small danger'>吊销</button></a></td></tr>"

        html = ADMIN_HTML
        html = html.replace("UPTIME", f"{(time.time()-self._started_at):.0f}")
        html = html.replace("REQS", str(self._request_count))
        html = html.replace("PEERS", str(len(PEER_STORE)))
        html = html.replace("ACCTS", str(len(ACCOUNT_STORE)))
        html = html.replace("¥COST", f"{total_cost:.2f}")
        html = html.replace("ACCOUNT_ROWS", account_rows or "<tr><td colspan=7>暂无账户</td></tr>")
        html = html.replace("COST_ROWS", cost_rows or "<tr><td colspan=6>暂无消费记录</td></tr>")
        html = html.replace("RELAY_ROWS", relay_rows or "<tr><td colspan=2>暂无其他中继服务器</td></tr>")
        html = html.replace("PEER_ROWS", peer_rows or "<tr><td colspan=5>暂无节点</td></tr>")
        html = html.replace("KEY_ROWS", key_rows or "<tr><td colspan=4>暂无Key</td></tr>")
        return web.Response(text=html, content_type="text/html")

    async def _admin_login(self, request: web.Request) -> web.Response:
        data = await request.post()
        username = data.get("username", "")
        password = data.get("password", "")
        account = ACCOUNT_STORE.get(username)
        if account and account["password_hash"] == _hash_password(password) and account.get("is_admin"):
            token = secrets.token_hex(16)
            SESSION_STORE[token] = username
            resp = web.HTTPFound("/admin")
            resp.set_cookie("admin_token", token, max_age=86400, httponly=True)
            return resp
        return web.Response(text=LOGIN_HTML.replace("ERR_MSG", "<p class=err>用户名或密码错误</p>"), content_type="text/html")

    async def _admin_logout(self, request: web.Request) -> web.Response:
        token = request.cookies.get("admin_token", "")
        SESSION_STORE.pop(token, None)
        resp = web.HTTPFound("/admin")
        resp.del_cookie("admin_token")
        return resp

    async def _admin_add_account(self, request: web.Request) -> web.Response:
        if not self._check_admin(request): return web.HTTPFound("/admin")
        data = await request.post()
        username = data.get("username", "").strip()
        password = data.get("password", "")
        if username and password and username not in ACCOUNT_STORE:
            ACCOUNT_STORE[username] = {"password_hash": _hash_password(password), "created": time.time(), "cost_rmb": 0.0, "token_in": 0, "token_out": 0, "last_login": 0, "is_admin": False, "cost_breakdown": {}}
            _save_accounts()
        raise web.HTTPFound("/admin")

    async def _admin_reset_password(self, request: web.Request) -> web.Response:
        if not self._check_admin(request): return web.HTTPFound("/admin")
        username = request.query.get("user", "")
        if username in ACCOUNT_STORE:
            new_pw = secrets.token_hex(4)
            ACCOUNT_STORE[username]["password_hash"] = _hash_password(new_pw)
            _save_accounts()
            logger.info(f"Password reset for {username}: {new_pw}")
        raise web.HTTPFound("/admin")

    async def _admin_delete_account(self, request: web.Request) -> web.Response:
        if not self._check_admin(request): return web.HTTPFound("/admin")
        username = request.query.get("user", "")
        if username in ACCOUNT_STORE and not ACCOUNT_STORE[username].get("is_admin"):
            del ACCOUNT_STORE[username]
            _save_accounts()
        raise web.HTTPFound("/admin")

    async def _admin_reset_stats(self, request: web.Request) -> web.Response:
        if not self._check_admin(request): return web.HTTPFound("/admin")
        scope = request.query.get("scope", "all")
        if scope in ("all", "peers"): PEER_STORE.clear()
        if scope in ("all", "costs"):
            for a in ACCOUNT_STORE.values():
                a["token_in"] = 0; a["token_out"] = 0; a["cost_rmb"] = 0.0; a["cost_breakdown"] = {}
            _save_accounts()
        if scope in ("all", "requests"): self._request_count = 0
        raise web.HTTPFound("/admin")

    async def _admin_add_relay(self, request: web.Request) -> web.Response:
        if not self._check_admin(request): return web.HTTPFound("/admin")
        data = await request.post()
        addr = data.get("address", "").strip()
        if addr and ":" in addr and addr not in RELAY_POOL and addr != f"{RELAY_HOST}:{RELAY_PORT}":
            RELAY_POOL.append(addr)
            _save_relay_pool()
            logger.info(f"Relay pool added: {addr}")
        raise web.HTTPFound("/admin")

    async def _admin_remove_relay(self, request: web.Request) -> web.Response:
        if not self._check_admin(request): return web.HTTPFound("/admin")
        addr = request.query.get("addr", "")
        if addr in RELAY_POOL:
            RELAY_POOL.remove(addr)
            _save_relay_pool()
        raise web.HTTPFound("/admin")

    async def _admin_add_key(self, request: web.Request) -> web.Response:
        if not self._check_admin(request): return web.HTTPFound("/admin")
        data = await request.post()
        name = data.get("name", "api-key").strip()[:30] or "api-key"
        key = f"lt-{secrets.token_hex(24)}"
        API_KEY_STORE[key] = {"name": name, "created": time.time(), "last_used": 0}
        raise web.HTTPFound("/admin")

    async def _admin_revoke_key(self, request: web.Request) -> web.Response:
        if not self._check_admin(request): return web.HTTPFound("/admin")
        partial = request.query.get("key", "")
        for key_val in list(API_KEY_STORE.keys()):
            if partial in key_val or key_val[:12] in partial:
                del API_KEY_STORE[key_val]; break
        raise web.HTTPFound("/admin")

    # ═══ API ═══

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "uptime": time.time() - self._started_at})

    async def _handle_status(self, request: web.Request) -> web.Response:
        user = self._check_auth(request)
        if not user: return web.json_response({"error": "Unauthorized"}, status=401)
        return web.json_response({"peers": len(PEER_STORE), "requests": self._request_count, "user": user})

    async def _handle_chat(self, request: web.Request) -> web.Response:
        user = self._check_auth(request)
        if not user: return web.json_response({"error": "请先登录 POST /login"}, status=401)
        self._request_count += 1
        try:
            data = await request.json()
            msg = data.get("message", data.get("prompt", ""))
            if not msg: return web.json_response({"error": "message required"}, status=400)
            if self._hub:
                result = await self._hub.chat(msg)
                return web.json_response({"response": result.get("response", str(result))})
            return web.json_response({"response": "Hub initializing..."})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _cost_report(self, request: web.Request) -> web.Response:
        """Client reports token consumption for cost tracking."""
        user = self._check_auth(request)
        if not user or user == "api": return web.json_response({"error": "Unauthorized"}, status=401)
        try:
            data = await request.json()
            provider = data.get("provider", "unknown")
            tokens_in = data.get("tokens_in", 0)
            tokens_out = data.get("tokens_out", 0)
            price = RMB_PER_M_TOKENS.get(provider, RMB_PER_M_TOKENS["default"])
            cost = (tokens_in + tokens_out) / 1_000_000 * price

            if user in ACCOUNT_STORE:
                a = ACCOUNT_STORE[user]
                a["token_in"] = a.get("token_in", 0) + tokens_in
                a["token_out"] = a.get("token_out", 0) + tokens_out
                a["cost_rmb"] = a.get("cost_rmb", 0.0) + cost
                cb = a.setdefault("cost_breakdown", {}).setdefault(provider, {"in": 0, "out": 0, "cost": 0.0})
                cb["in"] += tokens_in; cb["out"] += tokens_out; cb["cost"] += cost
                _save_accounts()
            return web.json_response({"status": "ok", "cost_rmb": cost})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    # ═══ P2P ═══

    async def _peer_register(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            peer_id = data.get("peer_id") or secrets.token_hex(8)
            username = data.get("metadata", {}).get("username", "")
            PEER_STORE[peer_id] = {"peer_id": peer_id, "ip": request.remote or "unknown", "port": data.get("port", 0), "nat_type": data.get("nat_type", "unknown"), "last_seen": time.time(), "metadata": data.get("metadata", {})}
            return web.json_response({"status": "registered", "peer_id": peer_id})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def _peer_discover(self, request: web.Request) -> web.Response:
        cutoff = time.time() - 300
        peers = {k: v for k, v in PEER_STORE.items() if v["last_seen"] > cutoff}
        return web.json_response({
            "peers": list(peers.values()), "count": len(peers),
            "relay_pool": [f"{RELAY_HOST}:{RELAY_PORT}"] + RELAY_POOL,
        })

    async def _ws_relay(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        client_id = secrets.token_hex(8)
        self._ws_clients[client_id] = ws
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    target = data.get("to", "")
                    if target in self._ws_clients:
                        await self._ws_clients[target].send_json({"from": client_id, "data": data.get("data", "")})
        finally:
            self._ws_clients.pop(client_id, None)
        return ws

    # ═══ WeChat ═══

    async def _wechat_verify(self, request: web.Request) -> web.Response:
        s, t, n, e = request.query.get("signature",""), request.query.get("timestamp",""), request.query.get("nonce",""), request.query.get("echostr","")
        token = os.environ.get("WECHAT_TOKEN", "livingtree")
        return web.Response(text=e if hashlib.sha1("".join(sorted([token,t,n])).encode()).hexdigest() == s else "fail")

    async def _wechat_message(self, request: web.Request) -> web.Response:
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(await request.text())
            msg = root.findtext("Content","").strip()
            reply = ""
            if msg and self._hub:
                result = await self._hub.chat(msg)
                reply = result.get("response",str(result))[:600]
            return web.Response(text=f"<xml><ToUserName><![CDATA[{root.findtext('FromUserName','')}]]></ToUserName><FromUserName><![CDATA[{root.findtext('ToUserName','')}]]></FromUserName><CreateTime>{int(time.time())}</CreateTime><MsgType><![CDATA[text]]></MsgType><Content><![CDATA[{reply}]]></Content></xml>", content_type="application/xml")
        except Exception:
            return web.Response(text="success")

    # ═══ Lifecycle ═══

    async def start(self):
        logger.info(f"🚀 Relay Server: {RELAY_HOST}:{self.port}")
        logger.info(f"👤 Accounts: {len(ACCOUNT_STORE)} | 🖥 Admin: http://{RELAY_HOST}:{self.port}/admin")

        # Auto-start opencode serve
        asyncio.create_task(self._auto_start_opencode())

        from livingtree.integration.hub import IntegrationHub
        self._hub = IntegrationHub(lazy=True)
        await self._hub.start()
        self._started_at = time.time()
        runner = web.AppRunner(self._app)
        await runner.setup()
        await web.TCPSite(runner, self.host, self.port).start()
        logger.info(f"✅ Ready")

    async def _auto_start_opencode(self):
        """Auto-start opencode serve in background."""
        try:
            from livingtree.tui.widgets.opencode_launcher import OpenCodeLauncher
            launcher = OpenCodeLauncher(workspace=str(PROJECT_ROOT))
            ok, msg = await launcher.auto_start_serve_if_needed()
            if ok:
                logger.info(f"OpenCode serve: {msg}")
        except Exception as e:
            logger.debug(f"OpenCode auto-start: {e}")

    async def shutdown(self):
        for ws in self._ws_clients.values(): await ws.close()
        if self._hub: await self._hub.shutdown()


async def run_server(port: int = 8888, host: str = "0.0.0.0"):
    server = P2PRelayServer(port=port, host=host)
    await server.start()
    try: await asyncio.Event().wait()
    except asyncio.CancelledError: await server.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LivingTree P2P Relay Server")
    parser.add_argument("--port", "-p", type=int, default=8888)
    parser.add_argument("--host", "-H", default="0.0.0.0")
    args = parser.parse_args()

    # ═══ Win2008 compatibility header ═══
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print(f"Event loop: {asyncio.get_event_loop().__class__.__name__}")
    print(f"Listening: {args.host}:{args.port}")
    print(f"Admin panel: http://www.mogoo.com.cn:{args.port}/admin" if args.port == 8888 else f"http://0.0.0.0:{args.port}/admin")
    print()

    try:
        asyncio.run(run_server(args.port, args.host))
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
    except Exception as e:
        print(f"\n[FATAL] {e}")
        print("\nWindows Server 2008 troubleshooting:")
        print("  1. Ensure VC++ 2015+ Redistributable is installed")
        print("  2. Run install_crt.bat if provided with the deployment package")
        print("  3. Check: https://aka.ms/vs/17/release/vc_redist.x64.exe")
        sys.exit(1)
