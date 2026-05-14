"""GitHub OAuth integration — login, list repos, clone, sync.

Flow:
  1. GET  /api/code/github/auth  → returns OAuth URL
  2. User authorizes → GitHub redirects to /api/code/github/callback
  3. POST /api/code/github/callback → exchange code for token → store encrypted
  4. GET  /api/code/github/status  → check if user is authenticated
  5. GET  /api/code/github/repos   → list user's repos
  6. POST /api/code/github/clone   → clone a repo as a project

Env vars:
    GITHUB_CLIENT_ID      - GitHub OAuth App client ID
    GITHUB_CLIENT_SECRET  - GitHub OAuth App client secret
    GITHUB_REDIRECT_URI   - OAuth callback URL (e.g. http://localhost:8100/api/code/github/callback)
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

import aiohttp
from fastapi import FastAPI, HTTPException, Depends, Query
from loguru import logger
from pydantic import BaseModel

from livingtree.api.auth import get_current_user, is_admin
from livingtree.api.audit import log_operation

# ═══ Config ═══

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.environ.get(
    "GITHUB_REDIRECT_URI", "http://localhost:8100/api/code/github/callback"
)
TOKEN_STORE = Path(__file__).resolve().parent.parent.parent / "data" / "github_tokens.json"

# ═══ Models ═══


class GitHubAuthResponse(BaseModel):
    url: str = ""
    authenticated: bool = False
    user: str = ""


class CloneRepoRequest(BaseModel):
    repo_url: str
    project_name: str
    branch: str = "main"


# ═══ Token Store ═══


def _load_tokens() -> dict[str, dict]:
    TOKEN_STORE.parent.mkdir(parents=True, exist_ok=True)
    if TOKEN_STORE.exists():
        try:
            return json.loads(TOKEN_STORE.read_text())
        except Exception:
            pass
    return {}


def _save_token(user_id: str, token_data: dict) -> None:
    tokens = _load_tokens()
    tokens[user_id] = {
        **token_data,
        "updated_at": time.time(),
    }
    TOKEN_STORE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_STORE.write_text(json.dumps(tokens, ensure_ascii=False, indent=2))


def _get_token(user_id: str) -> Optional[str]:
    tokens = _load_tokens()
    data = tokens.get(user_id, {})
    return data.get("access_token")


# ═══ GitHub API Helpers ═══


async def _github_api(path: str, token: str, method: str = "GET", body: dict = None) -> dict:
    """Call GitHub REST API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "LivingTree-AI-Agent",
    }
    url = f"https://api.github.com{path}"
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            async with session.get(url, headers=headers) as resp:
                return await resp.json()
        elif method == "POST":
            headers["Content-Type"] = "application/json"
            async with session.post(url, headers=headers, json=body or {}) as resp:
                return await resp.json()
    return {}


# ═══ Route Registration ═══


def setup_github_routes(app: FastAPI) -> None:

    @app.get("/api/code/github/auth", response_model=GitHubAuthResponse)
    async def github_auth(
        user: dict = Depends(get_current_user),
    ):
        """Get OAuth URL or check auth status."""
        token = _get_token(user["user_id"])
        if token:
            # Already authenticated — verify
            try:
                user_info = await _github_api("/user", token)
                if user_info.get("login"):
                    return GitHubAuthResponse(
                        authenticated=True,
                        user=user_info["login"],
                    )
            except Exception:
                pass  # Token expired, fall through

        if not GITHUB_CLIENT_ID:
            return GitHubAuthResponse(
                url="", authenticated=False, user=""
            )

        url = (
            f"https://github.com/login/oauth/authorize"
            f"?client_id={GITHUB_CLIENT_ID}"
            f"&redirect_uri={GITHUB_REDIRECT_URI}"
            f"&scope=repo"
            f"&state={user['user_id']}"
        )
        return GitHubAuthResponse(url=url, authenticated=False, user="")

    @app.get("/api/code/github/callback")
    async def github_callback(
        code: str = Query(...),
        state: str = Query(default=""),
    ):
        """OAuth callback — exchange code for token."""
        if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
            raise HTTPException(status_code=500, detail="GitHub OAuth not configured")

        user_id = state or "default"

        try:
            async with aiohttp.ClientSession() as session:
                # Exchange code for token
                async with session.post(
                    "https://github.com/login/oauth/access_token",
                    json={
                        "client_id": GITHUB_CLIENT_ID,
                        "client_secret": GITHUB_CLIENT_SECRET,
                        "code": code,
                        "redirect_uri": GITHUB_REDIRECT_URI,
                    },
                    headers={"Accept": "application/json"},
                ) as resp:
                    data = await resp.json()
                    if "error" in data:
                        raise HTTPException(status_code=400, detail=f"GitHub auth error: {data['error']}")

                    access_token = data.get("access_token")
                    if not access_token:
                        raise HTTPException(status_code=400, detail="No access token returned")

                    _save_token(user_id, {
                        "access_token": access_token,
                        "scope": data.get("scope", ""),
                        "token_type": data.get("token_type", "bearer"),
                    })

                    logger.info(f"GitHub OAuth: user {user_id} authenticated")
                    log_operation(user_id, "", "auth.github_login",
                                  details=f"GitHub OAuth 登录成功")
                    return {"ok": True, "message": "GitHub 登录成功，请关闭此页面"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"GitHub OAuth callback error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/code/github/status", response_model=GitHubAuthResponse)
    async def github_status(
        user: dict = Depends(get_current_user),
    ):
        """Check GitHub auth status."""
        token = _get_token(user["user_id"])
        if not token:
            return GitHubAuthResponse(authenticated=False, user="")

        try:
            user_info = await _github_api("/user", token)
            if user_info.get("login"):
                return GitHubAuthResponse(
                    authenticated=True, user=user_info["login"]
                )
        except Exception:
            pass

        return GitHubAuthResponse(authenticated=False, user="")

    @app.get("/api/code/github/repos")
    async def github_repos(
        user: dict = Depends(get_current_user),
    ):
        """List user's GitHub repositories."""
        token = _get_token(user["user_id"])
        if not token:
            raise HTTPException(status_code=401, detail="请先登录 GitHub")

        repos = await _github_api("/user/repos?per_page=50&sort=updated", token)
        if isinstance(repos, dict) and "message" in repos:
            raise HTTPException(status_code=400, detail=repos["message"])

        return [
            {
                "name": r["full_name"],
                "description": r.get("description", ""),
                "url": r["clone_url"],
                "stars": r.get("stargazers_count", 0),
                "language": r.get("language", ""),
                "updated_at": r.get("updated_at", ""),
            }
            for r in (repos if isinstance(repos, list) else [])
        ]

    @app.post("/api/code/github/clone")
    async def github_clone(
        req: CloneRepoRequest,
        user: dict = Depends(get_current_user),
    ):
        """Clone a GitHub repo as a new project."""
        token = _get_token(user["user_id"])
        if not token:
            raise HTTPException(status_code=401, detail="请先登录 GitHub")

        from .code_api import _get_project_dir, _project_exists, _save_projects, _load_projects

        user_id = user["user_id"]
        if _project_exists(user_id, req.project_name):
            raise HTTPException(status_code=400, detail=f"项目 '{req.project_name}' 已存在")

        proj_dir = _get_project_dir(user_id, req.project_name)

        # Build authenticated clone URL
        clone_url = req.repo_url
        if clone_url.startswith("https://"):
            clone_url = clone_url.replace(
                "https://", f"https://{token}@", 1
            )

        try:
            try:
                from livingtree.treellm.unified_exec import git
                result = await git(f"clone --branch {req.branch} {clone_url} {str(proj_dir)}", timeout=180)
                stdout = result.stdout
                exit_code = result.exit_code
                if exit_code != 0:
                    raise HTTPException(
                        status_code=500,
                        detail=f"克隆失败: {result.stderr[:300]}",
                    )
            except ImportError:
                result = subprocess.run(
                    ["git", "clone", "--branch", req.branch, clone_url, str(proj_dir)],
                    capture_output=True, text=True, timeout=180,
                )
                stdout = result.stdout
                if result.returncode != 0:
                    raise HTTPException(
                        status_code=500,
                        detail=f"克隆失败: {result.stderr[:300]}",
                    )

            projects = _load_projects()
            projects.append({
                "name": req.project_name,
                "owner": user_id,
                "created_at": time.time(),
                "github_url": req.repo_url,
                "github_branch": req.branch,
                "last_synced": time.time(),
                "doc_count": 0,
            })
            _save_projects(projects)

            logger.info(f"GitHub clone: {req.repo_url} → project '{req.project_name}' by {user['user_id']}")
            log_operation(user_id, user.get("name", ""), "repo.clone",
                          project=req.project_name,
                          details=f"克隆 GitHub 仓库 {req.repo_url} → {req.project_name}")

            # Background memory
            try:
                from livingtree.core.session_memory import agent_memory
                import asyncio as _asyncio
                loop = _asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(agent_memory.remember(
                        f"从 GitHub 克隆了仓库 {req.repo_url} 到项目 '{req.project_name}'",
                        user_id=user_id, project=req.project_name))
            except Exception:
                pass

            return {
                "ok": True,
                "project": req.project_name,
                "output": stdout[:500],
            }

        except HTTPException:
            raise
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="Git 克隆超时")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"克隆失败: {e}")


def _check_admin(user: dict):
    if not is_admin(user["user_id"]):
        raise HTTPException(status_code=403, detail="需要管理员权限")
