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

def _load_secret(key: str, default: str = "") -> str:
    """Load a secret from encrypted vault."""
    try:
        from ..config.secrets import get_secret_vault
        return get_secret_vault().get(key, default)
    except Exception:
        return default


CORP_ID = os.environ.get("WEWORK_CORP_ID", "")
AGENT_ID = os.environ.get("WEWORK_AGENT_ID", "")
APP_SECRET = os.environ.get("WEWORK_APP_SECRET", "")
TOKEN_SECRET = os.environ.get("JWT_SECRET", "") or _load_secret("jwt_secret", "")
TOKEN_EXPIRE = 86400 * 7  # 7 days

if not TOKEN_SECRET:
    logger.warning("JWT_SECRET not set — auth tokens will be insecure. Set env JWT_SECRET or add jwt_secret to vault.")

# Admin detection: configurable rules
WEWORK_ADMIN_USERS = os.environ.get("WEWORK_ADMIN_USERS", "").split(",") if os.environ.get("WEWORK_ADMIN_USERS") else []
WEWORK_ADMIN_DEPTS = os.environ.get("WEWORK_ADMIN_DEPTS", "1").split(",")  # default: dept_id=1
WEWORK_SUPERADMIN = os.environ.get("WEWORK_SUPERADMIN", "")  # always-admin user_id

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

def get_or_create_user(user_id: str, name: str = "", avatar: str = "", is_admin: bool | None = None) -> dict:
    """Create or update user. `is_admin` from WeChat Work overrides fallback logic."""
    users = _load_users()
    if user_id not in users:
        # Determine role: external decision > fallback (first user)
        if is_admin is None:
            is_admin = len(users) == 0
        users[user_id] = {
            "user_id": user_id, "name": name or f"用户{user_id[:6]}",
            "avatar": avatar, "created_at": time.time(),
            "last_login": time.time(),
            "role": "admin" if is_admin else "member",
        }
    else:
        users[user_id]["last_login"] = time.time()
        if name:
            users[user_id]["name"] = name
        if avatar:
            users[user_id]["avatar"] = avatar
        # If externally marked as admin, upgrade role
        if is_admin and users[user_id].get("role") != "admin":
            users[user_id]["role"] = "admin"
            logger.info(f"User {user_id} role upgraded to admin via WeChat Work")
        # Ensure role field exists (migration)
        if "role" not in users[user_id]:
            users[user_id]["role"] = "admin" if len(users) <= 1 else "member"
    _save_users(users)
    return users[user_id]


def is_admin(user_id: str) -> bool:
    """Check if a user has admin role."""
    users = _load_users()
    return users.get(user_id, {}).get("role") == "admin"


def get_all_users() -> list[dict]:
    """Get all users (admin only)."""
    users = _load_users()
    return list(users.values())


def set_user_role(user_id: str, role: str) -> bool:
    """Set a user's role (admin only). admin|member."""
    if role not in ("admin", "member"):
        return False
    users = _load_users()
    if user_id not in users:
        return False
    users[user_id]["role"] = role
    _save_users(users)
    return True

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
    return await _code_to_userid_oauth(code)


async def _get_user_detail(user_id: str) -> Optional[dict]:
    """Call user/get to get full user info: name, avatar, department, isleader."""
    token = await _get_access_token()
    if not token:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            url = (
                f"https://qyapi.weixin.qq.com/cgi-bin/user/get"
                f"?access_token={token}&userid={user_id}"
            )
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("errcode") == 0:
                    return {
                        "user_id": data.get("userid", user_id),
                        "name": data.get("name", ""),
                        "avatar": data.get("avatar", ""),
                        "department": data.get("department", []),
                        "isleader": data.get("isleader", 0),
                        "position": data.get("position", ""),
                        "mobile": data.get("mobile", ""),
                    }
                logger.warning(f"user/get failed for {user_id}: {data}")
    except Exception as e:
        logger.error(f"user/get failed for {user_id}: {e}")
    return None


def _determine_role(user_detail: dict) -> str:
    """Determine if a user should be admin based on WeChat Work info.

    Rules (first match wins):
    1. WEWORK_SUPERADMIN env → admin (hardcoded override)
    2. WEWORK_ADMIN_USERS list → admin
    3. isleader=1 AND department in WEWORK_ADMIN_DEPTS → admin
    4. department contains admin dept AND position contains keywords → admin
    5. First user in system → admin (fallback)
    6. Everyone else → member
    """
    user_id = user_detail.get("user_id", "")

    # Rule 1: superadmin override
    if WEWORK_SUPERADMIN and user_id == WEWORK_SUPERADMIN:
        logger.info(f"Admin via SUPERADMIN: {user_id}")
        return "admin"

    # Rule 2: explicit admin list
    if user_id in WEWORK_ADMIN_USERS:
        logger.info(f"Admin via WEWORK_ADMIN_USERS: {user_id}")
        return "admin"

    # Rule 3: isleader in admin dept
    is_leader = user_detail.get("isleader", 0)
    departments = user_detail.get("department", [])
    if is_leader and departments:
        for d in departments:
            if str(d) in WEWORK_ADMIN_DEPTS:
                logger.info(f"Admin via isleader+dept: {user_id} dept={d}")
                return "admin"

    # Rule 4: position-based (keywords that indicate management role)
    position = user_detail.get("position", "")
    admin_keywords = ["管理", "经理", "主管", "总监", "admin", "负责人", "主任"]
    if any(kw in position for kw in admin_keywords) and departments:
        for d in departments:
            if str(d) in WEWORK_ADMIN_DEPTS:
                logger.info(f"Admin via position+dept: {user_id} pos={position}")
                return "admin"

    # Rule 5: fallback - first user
    users = _load_users()
    if len(users) == 0:
        logger.info(f"Admin via first-user fallback: {user_id}")
        return "admin"

    return "member"

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

        # Fetch full WeChat Work user info to determine admin role
        user_detail = None
        is_admin = None
        if CORP_ID and not user_id.startswith("dev_"):
            user_detail = await _get_user_detail(user_id)
            if user_detail:
                is_admin = _determine_role(user_detail) == "admin"

        name = user_detail.get("name", "") if user_detail else ""
        avatar = user_detail.get("avatar", "") if user_detail else ""
        user = get_or_create_user(user_id, name=name, avatar=avatar, is_admin=is_admin)

        token = create_token(user_id, user.get("name", user_id))
        return LoginResponse(
            token=token, user_id=user_id,
            name=user.get("name", user_id), avatar=user.get("avatar", ""),
        )

    @app.get("/api/login/me")
    async def get_me(user: dict = Depends(get_current_user)) -> dict:
        """Get current user info including role."""
        users = _load_users()
        u = users.get(user["user_id"], user)
        return {
            "user_id": u["user_id"],
            "name": u.get("name", ""),
            "avatar": u.get("avatar", ""),
            "role": u.get("role", "member"),
        }

    @app.get("/api/user/me")
    async def user_me(user: dict = Depends(get_current_user)) -> dict:
        """Get current user info with role (alias)."""
        users = _load_users()
        u = users.get(user["user_id"], user)
        return {
            "user_id": u["user_id"],
            "name": u.get("name", ""),
            "avatar": u.get("avatar", ""),
            "role": u.get("role", "member"),
        }

    @app.get("/api/admin/users")
    async def list_users(user: dict = Depends(get_current_user)) -> list[dict]:
        """List all users (admin only)."""
        if not is_admin(user["user_id"]):
            raise HTTPException(status_code=403, detail="需要管理员权限")
        users = _load_users()
        return [
            {
                "user_id": u["user_id"],
                "name": u.get("name", ""),
                "avatar": u.get("avatar", ""),
                "role": u.get("role", "member"),
                "last_login": u.get("last_login", 0),
            }
            for u in users.values()
        ]

    class SetRoleRequest(BaseModel):
        user_id: str
        role: str  # admin | member

    @app.post("/api/admin/set-role")
    async def set_role(req: SetRoleRequest, user: dict = Depends(get_current_user)) -> dict:
        """Set a user's role (admin only)."""
        if not is_admin(user["user_id"]):
            raise HTTPException(status_code=403, detail="需要管理员权限")
        ok = set_user_role(req.user_id, req.role)
        if not ok:
            raise HTTPException(status_code=400, detail="用户不存在或角色无效")
        logger.info(f"User {user['user_id']} set role of {req.user_id} to {req.role}")
        return {"ok": True}

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
