"""Workspace — multi-user collaboration with role-based access control.

Workspace layout:
    output/workspaces/{workspace_id}/code/{project_name}/   ← shared projects

Role levels:
    owner   — full control (delete workspace, manage members, all projects)
    editor  — read/write files, create projects
    viewer  — read only

Data store:
    data/workspaces.json  — workspace metadata and memberships
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from livingtree.api.auth import get_current_user, is_admin
from livingtree.api.audit import log_operation

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
WORKSPACES_FILE = DATA_DIR / "workspaces.json"
OUTPUT_DIR = PROJECT_ROOT / "output"

ROLES = ["owner", "editor", "viewer"]

# ═══ Models ═══

class WorkspaceInfo(BaseModel):
    workspace_id: str
    name: str
    owner: str
    owner_name: str = ""
    role: str = ""
    member_count: int = 0
    project_count: int = 0
    created_at: float = 0.0

class CreateWorkspaceRequest(BaseModel):
    name: str

class InviteMemberRequest(BaseModel):
    user_id: str
    role: str = "editor"

class RemoveMemberRequest(BaseModel):
    user_id: str

# ═══ Storage ═══

def _load_workspaces() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if WORKSPACES_FILE.exists():
        try:
            return json.loads(WORKSPACES_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_workspaces(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ═══ Path Helpers ═══

def _get_workspace_dir(workspace_id: str) -> Path:
    return OUTPUT_DIR / "workspaces" / workspace_id


def _get_workspace_project_dir(workspace_id: str, project_name: str) -> Path:
    return _get_workspace_dir(workspace_id) / "code" / project_name


# ═══ Permission Helpers ═══

def get_user_role(workspace_id: str, user_id: str) -> Optional[str]:
    """Get a user's role in a workspace. Returns None if not a member."""
    data = _load_workspaces()
    ws = data.get(workspace_id)
    if not ws:
        return None
    members = ws.get("members", {})
    member = members.get(user_id)
    return member.get("role") if member else None


def check_workspace_access(workspace_id: str, user_id: str, min_role: str = "viewer") -> str:
    """Check user has at least min_role in workspace. Returns the user's role or raises 403."""
    role = get_user_role(workspace_id, user_id)
    if role is None:
        raise HTTPException(status_code=403, detail="你不是该工作空间的成员")
    role_index = ROLES.index(role)
    min_index = ROLES.index(min_role)
    if role_index > min_index:
        raise HTTPException(status_code=403, detail=f"需要 {min_role} 或更高权限")
    return role


def check_project_access(user_id: str, project_meta: dict, min_role: str = "viewer") -> str:
    """Check access to a project (either owner or workspace member). Returns effective role."""
    owner = project_meta.get("owner", "")
    ws_id = project_meta.get("workspace_id", "")
    if owner == user_id:
        return "owner"
    if ws_id:
        return check_workspace_access(ws_id, user_id, min_role)
    raise HTTPException(status_code=403, detail="无权访问此项目")


def _get_project_base_path(user_id: str, project_meta: dict) -> Path:
    """Get the filesystem path for a project (private or workspace)."""
    ws_id = project_meta.get("workspace_id", "")
    name = project_meta["name"]
    if ws_id:
        return _get_workspace_project_dir(ws_id, name)
    return OUTPUT_DIR / user_id / "code" / name


# ═══ Route Registration ═══

def setup_workspace_routes(app: FastAPI) -> None:

    @app.post("/api/workspaces", response_model=WorkspaceInfo)
    async def create_workspace(
        req: CreateWorkspaceRequest,
        user: dict = Depends(get_current_user),
    ):
        """Create a new workspace."""
        user_id = user["user_id"]
        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="工作空间名不能为空")

        ws_id = f"ws_{uuid.uuid4().hex[:12]}"
        now = time.time()

        data = _load_workspaces()
        data[ws_id] = {
            "workspace_id": ws_id,
            "name": name,
            "owner": user_id,
            "members": {
                user_id: {"role": "owner", "joined_at": now},
            },
            "created_at": now,
        }
        _save_workspaces(data)

        log_operation(user_id, user.get("name", ""), "workspace.create",
                      metadata={"workspace_id": ws_id, "workspace_name": name},
                      details=f"创建工作空间 '{name}'")

        logger.info(f"Workspace '{name}' ({ws_id}) created by {user_id}")
        return WorkspaceInfo(
            workspace_id=ws_id,
            name=name,
            owner=user_id,
            owner_name=user.get("name", ""),
            role="owner",
            member_count=1,
            project_count=0,
            created_at=now,
        )

    @app.get("/api/workspaces", response_model=list[WorkspaceInfo])
    async def list_workspaces(
        user: dict = Depends(get_current_user),
    ):
        """List workspaces the current user belongs to."""
        user_id = user["user_id"]
        data = _load_workspaces()
        result = []
        for ws_id, ws in data.items():
            members = ws.get("members", {})
            member = members.get(user_id)
            if not member and not is_admin(user_id):
                continue
            owner = ws.get("owner", "")
            owner_name = ""
            if owner and owner in members:
                owner_name = members[owner].get("display_name", "")
            project_count = len(ws.get("projects", []))

            result.append(WorkspaceInfo(
                workspace_id=ws_id,
                name=ws.get("name", ""),
                owner=owner,
                owner_name=owner_name,
                role=member.get("role", "admin_view") if member else "admin_view",
                member_count=len(members),
                project_count=project_count,
                created_at=ws.get("created_at", 0),
            ))
        return sorted(result, key=lambda w: w.created_at, reverse=True)

    @app.get("/api/workspaces/{workspace_id}", response_model=WorkspaceInfo)
    async def get_workspace(
        workspace_id: str,
        user: dict = Depends(get_current_user),
    ):
        """Get workspace details."""
        user_id = user["user_id"]
        check_workspace_access(workspace_id, user_id)

        data = _load_workspaces()
        ws = data.get(workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="工作空间不存在")

        members = ws.get("members", {})
        return WorkspaceInfo(
            workspace_id=workspace_id,
            name=ws["name"],
            owner=ws.get("owner", ""),
            role=members[user_id]["role"],
            member_count=len(members),
            project_count=len(ws.get("projects", [])),
            created_at=ws.get("created_at", 0),
        )

    @app.delete("/api/workspaces/{workspace_id}")
    async def delete_workspace(
        workspace_id: str,
        user: dict = Depends(get_current_user),
    ):
        """Delete a workspace (owner only)."""
        user_id = user["user_id"]
        check_workspace_access(workspace_id, user_id, "owner")

        data = _load_workspaces()
        ws = data.get(workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="工作空间不存在")

        name = ws.get("name", "")
        del data[workspace_id]
        _save_workspaces(data)

        # Clean up workspace directory
        ws_dir = _get_workspace_dir(workspace_id)
        import shutil
        shutil.rmtree(ws_dir, ignore_errors=True)

        log_operation(user_id, user.get("name", ""), "workspace.delete",
                      metadata={"workspace_id": workspace_id, "workspace_name": name},
                      details=f"删除工作空间 '{name}'")

        return {"ok": True, "workspace_id": workspace_id}

    @app.post("/api/workspaces/{workspace_id}/members", response_model=dict)
    async def invite_member(
        workspace_id: str,
        req: InviteMemberRequest,
        user: dict = Depends(get_current_user),
    ):
        """Invite a user to a workspace (owner or admin)."""
        inviter_id = user["user_id"]
        role = check_workspace_access(workspace_id, inviter_id)
        if role != "owner" and not is_admin(inviter_id):
            raise HTTPException(status_code=403, detail="只有工作空间所有者可以邀请成员")

        if req.role not in ROLES:
            raise HTTPException(status_code=400, detail=f"角色必须是: {', '.join(ROLES)}")

        data = _load_workspaces()
        ws = data.get(workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="工作空间不存在")

        members = ws.get("members", {})
        if req.user_id in members and req.user_id != inviter_id:
            raise HTTPException(status_code=400, detail="用户已是成员")

        from livingtree.api.auth import get_or_create_user
        target_user = get_or_create_user(req.user_id)

        members[req.user_id] = {
            "role": req.role,
            "joined_at": time.time(),
            "display_name": target_user.get("name", ""),
        }
        _save_workspaces(data)

        log_operation(inviter_id, user.get("name", ""), "workspace.invite",
                      metadata={
                          "workspace_id": workspace_id,
                          "target_user": req.user_id,
                          "role": req.role,
                      },
                      details=f"邀请 {req.user_id} 作为 {req.role} 加入工作空间")

        return {
            "ok": True,
            "user_id": req.user_id,
            "role": req.role,
            "display_name": target_user.get("name", ""),
        }

    @app.delete("/api/workspaces/{workspace_id}/members/{target_user_id}")
    async def remove_member(
        workspace_id: str,
        target_user_id: str,
        user: dict = Depends(get_current_user),
    ):
        """Remove a member from workspace (owner only, or self-remove)."""
        user_id = user["user_id"]
        is_self = user_id == target_user_id

        if not is_self:
            check_workspace_access(workspace_id, user_id, "owner")

        data = _load_workspaces()
        ws = data.get(workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="工作空间不存在")

        members = ws.get("members", {})
        if target_user_id not in members:
            raise HTTPException(status_code=404, detail="用户不是成员")

        if members[target_user_id].get("role") == "owner" and not is_admin(user_id):
            raise HTTPException(status_code=403, detail="不能移除工作空间所有者")

        removed_role = members[target_user_id]["role"]
        del members[target_user_id]
        _save_workspaces(data)

        log_operation(user_id, user.get("name", ""), "workspace.remove_member",
                      metadata={
                          "workspace_id": workspace_id,
                          "target_user": target_user_id,
                          "role": removed_role,
                      },
                      details=f"从工作空间移除 {target_user_id}")

        return {"ok": True, "removed_user": target_user_id}

    @app.get("/api/workspaces/{workspace_id}/members")
    async def list_members(
        workspace_id: str,
        user: dict = Depends(get_current_user),
    ):
        """List workspace members."""
        check_workspace_access(workspace_id, user["user_id"])

        data = _load_workspaces()
        ws = data.get(workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="工作空间不存在")

        members = ws.get("members", {})
        return [
            {
                "user_id": uid,
                "role": m.get("role", ""),
                "display_name": m.get("display_name", ""),
                "joined_at": m.get("joined_at", 0),
            }
            for uid, m in members.items()
        ]

    logger.info("Workspace API routes registered")
