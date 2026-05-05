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

# ═══ External network status ═══
_external_ok: bool = False
GITHUB_CHECK = "github.com"
CHECK_INTERVAL = 30  # seconds

# ═══ Offline message queue ═══
OFFLINE_QUEUE: dict[str, list[dict]] = {}  # peer_id → [{from, data, time}, ...]
MAX_QUEUE_SIZE = 50

# ═══ User API keys (one per user) ═══
USER_KEYS: dict[str, str] = {}  # username → api_key

# RMB per 1M tokens (approximate)
RMB_PER_M_TOKENS = {
    "deepseek": 2.0, "siliconflow": 0.0, "mofang": 0.0,
    "longcat": 0.0, "zhipu": 0.0, "spark": 0.0,
    "xiaomi": 8.0, "aliyun": 4.0, "dmxapi": 3.5,
    "default": 4.0,
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
    # Auto-generate API keys for users who don't have one
    for name in ACCOUNT_STORE:
        if name not in USER_KEYS:
            USER_KEYS[name] = f"lt-{secrets.token_hex(24)}"
    _save_user_keys()

def _save_accounts():
    try:
        path = Path(".livingtree/relay_accounts.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(ACCOUNT_STORE, indent=2, ensure_ascii=False))
    except Exception:
        pass

def _hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

USER_KEYS_FILE = Path(".livingtree/user_keys.json")

def _save_user_keys():
    try:
        USER_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
        USER_KEYS_FILE.write_text(json.dumps(USER_KEYS))
    except Exception: pass

def _load_user_keys():
    global USER_KEYS
    try:
        if USER_KEYS_FILE.exists():
            USER_KEYS = json.loads(USER_KEYS_FILE.read_text())
    except Exception:
        pass


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
  <div class="metric"><div class="val">NET_STATUS</div><div class="lbl">外网</div></div>
</div>
<p><a href="/admin/logout" style="font-size:12px">退出登录</a></p>

<h2>🔒 修改管理员密码</h2>
PWD_MSG
<form class="add-form" method="POST" action="/admin/password">
  <input name="username" placeholder="管理员用户名" required>
  <input name="old_password" type="password" placeholder="旧密码" required>
  <input name="new_password" type="password" placeholder="新密码" required>
  <button type="submit">修改</button>
</form>

<h2>👤 账户管理</h2>
<form class="add-form" method="POST" action="/admin/accounts/add">
  <input name="username" placeholder="用户名" required>
  <input name="password" placeholder="密码" required>
  <button type="submit">+ 添加</button>
</form>
<table><tr><th>用户名</th><th>创建时间</th><th>Token输入</th><th>Token输出</th><th>累计费用(¥)</th><th>最后登录</th><th>API Key</th><th>操作</th></tr>
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
<div class="row">
<form method="POST" action="/admin/keys/add" style="flex:1" class="add-form">
  <input name="name" placeholder="Key名称" required style="flex:1">
  <button type="submit">+ 生成</button>
</form>
</div>
<p style="font-size:11px;color:#8b949e">点击Key值自动复制到剪贴板</p>
<script>
window._copyKeys=PASS_TO_JS
function copyKey(k){navigator.clipboard.writeText(k).then(()=>{var e=event.target;e.textContent='已复制!';setTimeout(()=>e.textContent=e.dataset.key,1500)}).catch(()=>prompt('复制:',k))}
</script>

<h2>📡 API端点</h2>
<div class="endpoint">POST /login — {"username":"","password":""} → {"token":"...","api_key":"lt-..."}</div>
<div class="endpoint">POST /chat — Authorization: Bearer &lt;api_key&gt; {"message":"..."}</div>
<div class="endpoint">POST /web/fetch — 中继帮节点抓取网页（需外网连通）</div>
<div class="endpoint">POST /web/search — 中继帮节点搜索（需外网连通）</div>
<div class="endpoint">POST /peers/register — P2P节点注册</div>
<div class="endpoint">GET /peers/discover — P2P节点发现</div>
<div class="endpoint">POST /peers/sync — 中继池同步</div>
<div class="endpoint">WS /ws/relay — WebSocket消息中继</div>
<div class="endpoint">POST /cost/report — 上报token消耗（需api_key）</div>
<div style="margin-top:15px">
<a href="/admin/stats/reset?scope=costs"><button class="danger">🗑 清空费用统计</button></a>
<a href="/admin/stats/reset?scope=peers"><button class="danger">🗑 清空节点列表</button></a>
<a href="/admin/stats/reset?scope=all"><button class="danger">🗑 清空全部统计</button></a>
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
        app.router.add_post("/admin/password", self._admin_change_password)
        # API (all require API key except /login and /health)
        app.router.add_get("/health", self._health)
        app.router.add_post("/chat", self._handle_chat)
        app.router.add_get("/status", self._handle_status)
        app.router.add_post("/cost/report", self._cost_report)
        # Web delegation (relay fetches for nodes)
        app.router.add_post("/web/fetch", self._web_fetch)
        app.router.add_post("/web/search", self._web_search)
        # P2P
        app.router.add_post("/peers/register", self._peer_register)
        app.router.add_get("/peers/discover", self._peer_discover)
        app.router.add_post("/peers/sync", self._peer_sync)
        app.router.add_get("/peers/best", self._peer_best_relay)
        app.router.add_get("/ws/relay", self._ws_relay)
        # Metrics
        app.router.add_get("/metrics", self._metrics)
        # WeChat
        app.router.add_get("/wechat", self._wechat_verify)
        app.router.add_post("/wechat", self._wechat_message)

    # ═══ Auth ═══

    def _check_auth(self, request: web.Request) -> str | None:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            # Check user-specific API keys first
            for username, key in USER_KEYS.items():
                if token == key:
                    return username
            # Legacy: session token
            for username, data in ACCOUNT_STORE.items():
                expected = hashlib.sha256(f"{username}:{data.get('password_hash','')}".encode()).hexdigest()[:32]
                if token == expected or token == data.get("session_token", ""):
                    return username
            # Global API keys (deprecated but kept for backward compat)
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
            # Return user's API key (auto-generated if needed)
            api_key = USER_KEYS.get(username, "")
            if not api_key:
                api_key = f"lt-{secrets.token_hex(24)}"
                USER_KEYS[username] = api_key
                _save_user_keys()
            return web.json_response({
                "token": token, "username": username,
                "node_id": f"lt-{username}",
                "api_key": api_key,
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    # ═══ Admin pages ═══

    async def _admin_login_page(self, request: web.Request) -> web.Response:
        return web.Response(text=LOGIN_HTML.replace("ERR_MSG", ""), content_type="text/html")

    async def _admin_page(self, request: web.Request) -> web.Response:
        if not self._check_admin(request):
            return web.Response(text=LOGIN_HTML.replace("ERR_MSG", ""), content_type="text/html")

        # Account rows with API key
        account_rows = ""
        for name, a in ACCOUNT_STORE.items():
            created = time.strftime("%m-%d %H:%M", time.localtime(a.get("created", 0)))
            last = time.strftime("%m-%d %H:%M", time.localtime(a.get("last_login", 0))) if a.get("last_login") else "-"
            ukey = USER_KEYS.get(name, "")
            key_display = ukey[:12] + "..." + ukey[-8:] if ukey else "-"
            reset_link = f"/admin/accounts/reset?user={name}"
            del_link = f"/admin/accounts/delete?user={name}"
            account_rows += f"<tr><td>{name}{' [管理员]' if a.get('is_admin') else ''}</td><td>{created}</td><td>{a.get('token_in',0):,}</td><td>{a.get('token_out',0):,}</td><td>¥{a.get('cost_rmb',0):.4f}</td><td>{last}</td><td><code data-key='{ukey}' onclick='copyKey(this.dataset.key)' style='cursor:pointer;font-size:11px' title='点击复制API Key'>{key_display} 📋</code></td><td><a href='{reset_link}'><button class='small'>改密</button></a> <a href='{del_link}' onclick='return confirm(\"删除{name}?\")'><button class='small danger'>删除</button></a></td></tr>"

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
        key_list = {}
        for key_val, info in API_KEY_STORE.items():
            display = key_val[:12] + "..." + key_val[-8:]
            key_list[display] = key_val
            created = time.strftime("%m-%d", time.localtime(info.get("created", 0)))
            revoke_key = key_val[:12] + key_val[-8:]  # use partial for revoke link
            key_rows += f"<tr><td>{info['name']}</td><td><code data-key='{key_val}' onclick='copyKey(this.dataset.key)' style='cursor:pointer' title='点击复制'>{display} 📋</code></td><td>{created}</td><td><a href='/admin/keys/revoke?key={display}'><button class='small danger'>吊销</button></a></td></tr>"

        html = ADMIN_HTML
        html = html.replace("PWD_MSG", "")
        html = html.replace("PASS_TO_JS", json.dumps(key_list))
        html = html.replace("UPTIME", f"{(time.time()-self._started_at):.0f}")
        html = html.replace("REQS", str(self._request_count))
        html = html.replace("PEERS", str(len(PEER_STORE)))
        html = html.replace("ACCTS", str(len(ACCOUNT_STORE)))
        html = html.replace("¥COST", f"{total_cost:.2f}")
        html = html.replace("NET_STATUS", "🟢OK" if _external_ok else "🔴断")
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

    async def _admin_change_password(self, request: web.Request) -> web.Response:
        if not self._check_admin(request): return web.HTTPFound("/admin")
        data = await request.post()
        username = data.get("username", "").strip()
        old_pass = data.get("old_password", "")
        new_pass = data.get("new_password", "")
        account = ACCOUNT_STORE.get(username)
        if not account or account["password_hash"] != _hash_password(old_pass):
            return web.Response(text=ADMIN_HTML.replace("UPTIME", "err")
                .replace("REQS", "").replace("PEERS", "").replace("ACCTS", "").replace("¥COST", "")
                .replace("ACCOUNT_ROWS", "").replace("COST_ROWS", "").replace("RELAY_ROWS", "")
                .replace("PEER_ROWS", "").replace("KEY_ROWS", "")
                .replace("PWD_MSG", "<p style=color:#f85149>旧密码错误</p>"), content_type="text/html")
        if len(new_pass) < 4:
            return web.Response(text=ADMIN_HTML.replace("UPTIME", "err")
                .replace("REQS", "").replace("PEERS", "").replace("ACCTS", "").replace("¥COST", "")
                .replace("ACCOUNT_ROWS", "").replace("COST_ROWS", "").replace("RELAY_ROWS", "")
                .replace("PEER_ROWS", "").replace("KEY_ROWS", "")
                .replace("PWD_MSG", "<p style=color:#f85149>新密码至少4位</p>"), content_type="text/html")
        account["password_hash"] = _hash_password(new_pass)
        _save_accounts()
        SESSION_STORE.clear()  # force re-login
        resp = web.HTTPFound("/admin")
        resp.del_cookie("admin_token")
        return resp

    # ═══ API ═══

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "ok", "uptime": time.time() - self._started_at,
            "external_ok": _external_ok, "peers": len(PEER_STORE),
        })

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

        # Replay offline queue for this peer
        queued = OFFLINE_QUEUE.pop(client_id, [])
        for m in queued:
            try:
                await ws.send_json({"from": "relay", "data": m.get("data",""), "queued": True})
            except Exception:
                break

        username = request.headers.get("X-Peer-Username", "")
        if username:
            # Also replay messages addressed to username
            for uname_q in [client_id, username, f"user:{username}"]:
                q = OFFLINE_QUEUE.pop(uname_q, [])
                for m in q:
                    try:
                        await ws.send_json({"from": "relay", "data": m.get("data",""), "queued": True})
                    except Exception:
                        break

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    target = data.get("to", "")
                    payload = data.get("data", "")
                    if target in self._ws_clients:
                        await self._ws_clients[target].send_json({"from": client_id, "data": payload})
                    else:
                        # Queue for offline delivery
                        queue = OFFLINE_QUEUE.setdefault(target, [])
                        queue.append({"from": client_id, "data": payload, "time": time.time()})
                        if len(queue) > MAX_QUEUE_SIZE:
                            queue = queue[-MAX_QUEUE_SIZE:]
                        # Also queue by user ID
                        user_target = data.get("user", "")
                        if user_target:
                            uq = OFFLINE_QUEUE.setdefault(f"user:{user_target}", [])
                            uq.append({"from": client_id, "data": payload, "time": time.time()})
                            if len(uq) > MAX_QUEUE_SIZE:
                                uq = uq[-MAX_QUEUE_SIZE:]
        finally:
            self._ws_clients.pop(client_id, None)
        return ws

    # ═══ Web delegation (nodes delegate fetch/search to relay) ═══

    async def _web_fetch(self, request: web.Request) -> web.Response:
        user = self._check_auth(request)
        if not user: return web.json_response({"error": "Unauthorized — need API key"}, status=401)
        if not _external_ok: return web.json_response({"error": "Relay has no external network access"}, status=503)
        try:
            data = await request.json()
            url = data.get("url", "")
            if not url: return web.json_response({"error": "url required"}, status=400)
            import urllib.request, re
            req = urllib.request.Request(url, headers={"User-Agent": "LivingTreeRelay/2.1"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            # Strip to text
            clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL|re.IGNORECASE)
            clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL|re.IGNORECASE)
            clean = re.sub(r'<[^>]+>', ' ', clean)
            clean = re.sub(r'\s+', ' ', clean)
            return web.json_response({"content": clean[:30000], "url": url})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _web_search(self, request: web.Request) -> web.Response:
        user = self._check_auth(request)
        if not user: return web.json_response({"error": "Unauthorized — need API key"}, status=401)
        if not _external_ok: return web.json_response({"error": "Relay has no external network access"}, status=503)
        try:
            data = await request.json()
            query = data.get("query", "")
            if not query: return web.json_response({"error": "query required"}, status=400)
            try:
                from livingtree.search.spark_search import SparkSearch
                results = SparkSearch().search(query, limit=data.get("limit", 5))
                return web.json_response({"results": results, "query": query})
            except Exception:
                pass
            # Fallback: DuckDuckGo HTML search
            import urllib.request, urllib.parse, re
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "LivingTreeRelay/2.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            results = []
            for m in re.finditer(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL):
                results.append({"url": m.group(1), "title": re.sub(r'<[^>]+>', '', m.group(2)).strip()})
            return web.json_response({"results": results[:5], "query": query})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    # ═══ Relay pool sync ═══

    async def _peer_sync(self, request: web.Request) -> web.Response:
        """Relay servers push/pull their pool lists to each other."""
        try:
            data = await request.json()
            remote_pool = data.get("pool", [])
            remote_addr = data.get("address", "")
            # Merge: add remote relays we don't know about
            added = 0
            for addr in remote_pool:
                if addr and addr not in RELAY_POOL and addr != f"{RELAY_HOST}:{RELAY_PORT}":
                    RELAY_POOL.append(addr)
                    added += 1
            if added:
                _save_relay_pool()
                logger.info(f"Sync: +{added} relays from {remote_addr}")
            # Return our pool so they can sync too
            return web.json_response({
                "pool": [f"{RELAY_HOST}:{RELAY_PORT}"] + RELAY_POOL,
                "added": added,
                "external_ok": _external_ok,
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    # ═══ Connectivity heartbeat ═══

    async def _connectivity_check(self):
        """Periodic GitHub connectivity check."""
        global _external_ok
        while True:
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(GITHUB_CHECK, 443),
                    timeout=5,
                )
                writer.close()
                await writer.wait_closed()
                _external_ok = True
            except Exception:
                _external_ok = False
            await asyncio.sleep(CHECK_INTERVAL)

    async def _sync_relay_pool(self):
        """Periodically push relay pool to other relays in the pool."""
        await asyncio.sleep(10)  # initial delay
        while True:
            if _external_ok:
                my_pool = [f"{RELAY_HOST}:{RELAY_PORT}"] + RELAY_POOL
                for addr in RELAY_POOL[:]:
                    try:
                        host, port = addr.rsplit(":", 1)
                        async with aiohttp.ClientSession() as s:
                            async with s.post(
                                f"http://{host}:{port}/peers/sync",
                                json={"pool": my_pool, "address": f"{RELAY_HOST}:{RELAY_PORT}"},
                                timeout=aiohttp.ClientTimeout(total=5),
                            ) as resp:
                                if resp.status == 200:
                                    remote = await resp.json()
                                    for ra in remote.get("pool", []):
                                        if ra not in RELAY_POOL and ra != f"{RELAY_HOST}:{RELAY_PORT}":
                                            RELAY_POOL.append(ra)
                                            _save_relay_pool()
                    except Exception:
                        pass
            await asyncio.sleep(60)

    # ═══ Health routing ═══

    async def _peer_best_relay(self, request: web.Request) -> web.Response:
        """Return the best relay server based on load (fewer peers = preferred)."""
        my_peer_count = len(PEER_STORE)
        best = {"host": RELAY_HOST, "port": RELAY_PORT, "peers": my_peer_count, "external_ok": _external_ok}

        candidates = [best]
        for addr in RELAY_POOL:
            try:
                host, port = addr.rsplit(":", 1)
                async with aiohttp.ClientSession() as s:
                    async with s.get(
                        f"http://{host}:{port}/health",
                        timeout=aiohttp.ClientTimeout(total=3),
                    ) as resp:
                        if resp.status == 200:
                            d = await resp.json()
                            candidates.append({
                                "host": host, "port": int(port),
                                "peers": d.get("peers", 999),
                                "external_ok": d.get("external_ok", False),
                            })
            except Exception:
                pass

        # Prefer relays with external network, then lowest load
        candidates.sort(key=lambda r: (not r["external_ok"], r["peers"]))
        return web.json_response({"best": candidates[0] if candidates else best, "candidates": candidates})

    # ═══ Prometheus metrics ═══

    async def _metrics(self, request: web.Request) -> web.Response:
        """Prometheus /metrics endpoint for Grafana integration."""
        uptime = time.time() - self._started_at
        total_cost = sum(a.get("cost_rmb", 0) for a in ACCOUNT_STORE.values())
        total_tokens_in = sum(a.get("token_in", 0) for a in ACCOUNT_STORE.values())
        total_tokens_out = sum(a.get("token_out", 0) for a in ACCOUNT_STORE.values())
        queue_size = sum(len(v) for v in OFFLINE_QUEUE.values())

        lines = [
            "# HELP relay_uptime_seconds Relay server uptime",
            "# TYPE relay_uptime_seconds gauge",
            f"relay_uptime_seconds {uptime:.0f}",
            "# HELP relay_requests_total Total requests served",
            "# TYPE relay_requests_total counter",
            f"relay_requests_total {self._request_count}",
            "# HELP relay_peers_online Online P2P peers",
            "# TYPE relay_peers_online gauge",
            f"relay_peers_online {len(PEER_STORE)}",
            "# HELP relay_accounts_total Registered accounts",
            "# TYPE relay_accounts_total gauge",
            f"relay_accounts_total {len(ACCOUNT_STORE)}",
            "# HELP relay_external_ok External network reachable (1=yes)",
            "# TYPE relay_external_ok gauge",
            f"relay_external_ok {1 if _external_ok else 0}",
            "# HELP relay_tokens_in_total Total input tokens",
            "# TYPE relay_tokens_in_total counter",
            f"relay_tokens_in_total {total_tokens_in}",
            "# HELP relay_tokens_out_total Total output tokens",
            "# TYPE relay_tokens_out_total counter",
            f"relay_tokens_out_total {total_tokens_out}",
            "# HELP relay_cost_rmb_total Accumulated cost in RMB",
            "# TYPE relay_cost_rmb_total counter",
            f"relay_cost_rmb_total {total_cost:.4f}",
            "# HELP relay_ws_clients WebSocket clients",
            "# TYPE relay_ws_clients gauge",
            f"relay_ws_clients {len(self._ws_clients)}",
            "# HELP relay_offline_queue_size Pending offline messages",
            "# TYPE relay_offline_queue_size gauge",
            f"relay_offline_queue_size {queue_size}",
            "# HELP relay_pool_size Relay pool members",
            "# TYPE relay_pool_size gauge",
            f"relay_pool_size {len(RELAY_POOL) + 1}",
        ]
        # Per-user cost
        for name, a in ACCOUNT_STORE.items():
            safe = name.replace('"', '').replace("'", "")
            lines.append(f'# HELP relay_user_cost_rmb Cost for user {safe}')
            lines.append(f'# TYPE relay_user_cost_rmb gauge')
            lines.append(f'relay_user_cost_rmb{{user="{safe}"}} {a.get("cost_rmb",0):.4f}')

        return web.Response(text="\n".join(lines) + "\n", content_type="text/plain")

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
        _load_user_keys()
        logger.info(f"🚀 Relay Server: {RELAY_HOST}:{self.port}")
        logger.info(f"👤 Accounts: {len(ACCOUNT_STORE)} | 🔑 User keys: {len(USER_KEYS)}")
        logger.info(f"🖥 Admin: http://{RELAY_HOST}:{self.port}/admin")

        # Connectivity heartbeat
        asyncio.create_task(self._connectivity_check())
        # Relay pool auto-sync
        asyncio.create_task(self._sync_relay_pool())

        from livingtree.integration.hub import IntegrationHub
        self._hub = IntegrationHub(lazy=True)
        await self._hub.start()
        self._started_at = time.time()
        runner = web.AppRunner(self._app)
        await runner.setup()
        await web.TCPSite(runner, self.host, self.port).start()

        # Initial connectivity check
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(GITHUB_CHECK, 443), timeout=5)
            writer.close(); await writer.wait_closed()
            global _external_ok; _external_ok = True
        except Exception:
            pass

        logger.info(f"✅ Ready | External: {'OK' if _external_ok else 'OFFLINE'}")

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
