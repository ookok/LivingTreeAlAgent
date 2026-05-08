"""WeChat Work (企业微信) Login & Auth — self-built app.

Flow:
  在企微内 → OAuth2 静默授权 → code → /api/login/wework (type=oauth) → JWT
  在企微外 → 扫码登录 → code → /api/login/wework (type=qr) → JWT

All API calls require JWT in Authorization header.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import aiohttp
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from loguru import logger

# ═══ Config ═══
CORP_ID = os.environ.get("WEWORK_CORP_ID", "")
AGENT_ID = os.environ.get("WEWORK_AGENT_ID", "")
APP_SECRET = os.environ.get("WEWORK_APP_SECRET", "")
TOKEN_SECRET = os.environ.get("JWT_SECRET", "livingtree-wework-2026")
TOKEN_EXPIRE = 86400 * 7  # 7 days

AUTH_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "auth"
AUTH_DIR.mkdir(parents=True, exist_ok=True)
USERS_FILE = AUTH_DIR / "users.json"

# ═══ Models ═══

class LoginRequest(BaseModel):
    code: str
    login_type: str = "oauth"  # oauth | qr

class LoginResponse(BaseModel):
    token: str
    user_id: str
    name: str
    avatar: str = ""
    expires_in: int = TOKEN_EXPIRE

# ═══ Simple JWT (HMAC-SHA256, no PyJWT dep) ═══

def _b64url(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def _b64url_decode(s: str) -> bytes:
    import base64
    s += '=' * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)

def create_token(user_id: str, name: str) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({
        "user_id": user_id, "name": name,
        "iat": int(time.time()), "exp": int(time.time()) + TOKEN_EXPIRE,
    }).encode())
    import hmac
    sig_input = f"{header}.{payload}".encode()
    sig = _b64url(hmac.digest(TOKEN_SECRET.encode(), sig_input, hashlib.sha256))
    return f"{header}.{payload}.{sig}"

def verify_token(token: str) -> Optional[dict]:
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header, payload, sig = parts
        import hmac
        sig_input = f"{header}.{payload}".encode()
        expected = _b64url(hmac.digest(TOKEN_SECRET.encode(), sig_input, hashlib.sha256))
        if sig != expected:
            return None
        data = json.loads(_b64url_decode(payload))
        if data.get("exp", 0) < time.time():
            return None
        return data
    except Exception:
        return None

# ═══ User Store ═══

def _load_users() -> dict:
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text())
        except Exception:
            pass
    return {}

def _save_users(users: dict) -> None:
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2))

def get_or_create_user(user_id: str, name: str = "", avatar: str = "") -> dict:
    users = _load_users()
    if user_id not in users:
        users[user_id] = {
            "user_id": user_id, "name": name or f"用户{user_id[:6]}",
            "avatar": avatar, "created_at": time.time(),
            "last_login": time.time(),
        }
    else:
        users[user_id]["last_login"] = time.time()
        if name:
            users[user_id]["name"] = name
    _save_users(users)
    return users[user_id]

# ═══ WeChat Work API ═══

async def _get_access_token() -> Optional[str]:
    """Get enterprise access_token (cached for 2h)."""
    cache_file = AUTH_DIR / "access_token.json"
    now = time.time()
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            if cached.get("expires_at", 0) > now + 60:
                return cached["token"]
        except Exception:
            pass

    if not CORP_ID or not APP_SECRET:
        return None

    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={CORP_ID}&corpsecret={APP_SECRET}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("errcode") == 0:
                    token = data["access_token"]
                    cache_file.write_text(json.dumps({
                        "token": token, "expires_at": now + data.get("expires_in", 7200),
                    }))
                    return token
    except Exception as e:
        logger.warning(f"get_access_token failed: {e}")
    return None

async def _code_to_userid_oauth(code: str) -> Optional[dict]:
    """OAuth2: code → user/getuserinfo → {UserId, DeviceId, ...}"""
    token = await _get_access_token()
    if not token:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://qyapi.weixin.qq.com/cgi-bin/user/getuserinfo?access_token={token}&code={code}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("errcode") == 0:
                    return {"user_id": data["UserId"], "device_id": data.get("DeviceId", "")}
                logger.warning(f"getuserinfo failed: {data}")
    except Exception as e:
        logger.error(f"code_to_userid failed: {e}")
    return None

async def _code_to_userid_qr(code: str) -> Optional[dict]:
    """QR login: qrcode/check → {userid, ...}"""
    # For self-built app QR login, use the same oauth flow
    # The QR code generates a code that goes through the same getuserinfo
    return await _code_to_userid_oauth(code)

# ═══ Auth Middleware ═══

security = HTTPBearer(auto_error=False)

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return payload

def optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[dict]:
    if not credentials:
        return None
    return verify_token(credentials.credentials)

# ═══ Route Setup ═══

def setup_auth_routes(app: FastAPI) -> None:

    @app.post("/api/login/wework", response_model=LoginResponse)
    async def wework_login(req: LoginRequest, request: Request) -> LoginResponse:
        """Unified login: oauth or qr code → JWT token."""
        if not req.code:
            raise HTTPException(status_code=400, detail="code required")

        # Exchange code for user identity
        identity = None
        if req.login_type == "oauth":
            identity = await _code_to_userid_oauth(req.code)
        elif req.login_type == "qr":
            identity = await _code_to_userid_qr(req.code)

        # Dev mode: accept test codes
        if not identity and CORP_ID == "":
            identity = {"user_id": f"dev_{req.code[:12]}", "device_id": ""}

        if not identity:
            raise HTTPException(status_code=401, detail="登录失败，无效的授权码")

        user_id = identity["user_id"]
        user = get_or_create_user(user_id)

        token = create_token(user_id, user.get("name", user_id))
        return LoginResponse(
            token=token, user_id=user_id,
            name=user.get("name", user_id), avatar=user.get("avatar", ""),
        )

    @app.get("/api/login/me")
    async def get_me(user: dict = Depends(get_current_user)) -> dict:
        """Get current user info."""
        users = _load_users()
        u = users.get(user["user_id"], user)
        return {"user_id": u["user_id"], "name": u.get("name", ""), "avatar": u.get("avatar", "")}

    @app.get("/api/login/config")
    async def login_config() -> dict:
        """Return WeChat Work OAuth config for frontend."""
        redirect_uri = os.environ.get("WEWORK_REDIRECT_URI", "")
        return {
            "corp_id": CORP_ID,
            "agent_id": AGENT_ID,
            "redirect_uri": redirect_uri,
            "oauth_url": (
                f"https://open.weixin.qq.com/connect/oauth2/authorize"
                f"?appid={CORP_ID}&redirect_uri={redirect_uri}"
                f"&response_type=code&scope=snsapi_base&agentid={AGENT_ID}"
                f"#wechat_redirect"
            ) if CORP_ID else "",
        }

    logger.info("Auth routes registered (WeChat Work login)")
