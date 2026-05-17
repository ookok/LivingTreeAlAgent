"""HTMX Shell routes — sandboxed command execution panel.

Extracted from htmx_web.py.
Routes: POST /shell/exec, POST /shell/mount, GET /shell/panel
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

shell_router = APIRouter(prefix="/shell", tags=["shell"])


@shell_router.post("/exec")
async def shell_exec(request: Request):
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = {k: v for k, v in form.items()}
    command = body.get("command", body.get("cmd", body.get("message", "")))
    workdir = body.get("workdir", body.get("cwd", ""))
    mount = body.get("mount", body.get("mount_name", ""))
    if not command.strip():
        return HTMLResponse('<div style="color:var(--warn);font-size:12px">请输入命令</div>')
    from ..core.shell_env import get_shell
    shell = get_shell()
    result = await shell.execute(command, workdir=workdir, mount_name=mount)
    if result.blocked:
        return HTMLResponse(
            f'<div class="card" style="border-left:3px solid var(--err)">'
            f'<h3>🚫 命令已拦截</h3>'
            f'<pre style="font-size:11px;color:var(--err);white-space:pre-wrap">{result.block_reason}</pre></div>')
    status_color = "var(--accent)" if result.exit_code == 0 else "var(--err)"
    status_text = "✅ 成功" if result.exit_code == 0 else f"❌ 退出码 {result.exit_code}"
    output = result.stdout
    if result.stderr:
        output += ("\n" if output else "") + result.stderr
    return HTMLResponse(
        f'<div class="card">'
        f'<h3 style="display:flex;justify-content:space-between">'
        f'<span>{command[:80]}</span>'
        f'<span style="font-size:11px;color:{status_color}">{status_text} · {result.elapsed_ms:.0f}ms</span></h3>'
        f'<div style="font-size:10px;color:var(--dim);margin-bottom:4px">目录: {result.workdir}'
        + (f' · 截断' if result.truncated else '') + f'</div>'
        f'<pre style="background:rgba(0,0,0,.1);padding:8px;border-radius:4px;'
        f'font-size:11px;font-family:var(--font-mono);line-height:1.4;'
        f'white-space:pre-wrap;max-height:300px;overflow-y:auto;'
        f'color:var(--text)">{output[:5000] or "(无输出)"}</pre></div>')


@shell_router.post("/mount")
async def shell_mount(request: Request):
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = {k: v for k, v in form.items()}
    path_str = body.get("path", body.get("folder", body.get("message", "")))
    name = body.get("name", path_str.replace("\\", "/").split("/")[-1] if path_str else "mount")
    if not path_str:
        return HTMLResponse('<div style="color:var(--warn);font-size:12px">请输入文件夹路径</div>')
    from ..core.shell_env import get_shell
    shell = get_shell()
    m = shell.localfs.mount(name, path_str)
    if m:
        files = shell.localfs.list_files(name, max_depth=2)
        file_count = sum(1 for f in files if f.get("type") == "file")
        return HTMLResponse(
            f'<div class="card" style="border-left:3px solid var(--accent)">'
            f'<h3>📂 已挂载: {name}</h3>'
            f'<div style="font-size:11px;color:var(--dim)">{m.path}</div>'
            f'<div style="font-size:11px;margin-top:4px">{len(files)} 个条目 · {file_count} 个文件</div>'
            f'<div style="font-size:10px;color:var(--dim);margin-top:4px">可用: workdir="{name}" 或 mount_name="{name}" 在shell命令中</div></div>')
    return HTMLResponse(f'<div style="color:var(--err);font-size:12px">挂载失败: 路径不存在</div>')


@shell_router.get("/panel")
async def shell_panel(request: Request):
    return HTMLResponse(
        '<div class="card"><h2>💻 终端 · Shell 执行</h2>'
        '<p style="font-size:11px;color:var(--dim);margin-bottom:8px">在挂载的本地文件夹中执行命令。安全策略自动拦截危险操作。</p>'
        '<div style="display:flex;gap:4px;margin-bottom:8px">'
        '<input id="shell-mount-path" placeholder="挂载本地文件夹路径..." style="flex:1;font-size:11px;padding:6px 8px">'
        '<button onclick="mountFolder()" style="font-size:10px;padding:6px 10px;white-space:nowrap">📂 挂载</button></div>'
        '<div id="mount-result"></div>'
        '<div style="margin-top:8px;display:flex;gap:4px">'
        '<input id="shell-cmd" placeholder="命令..." style="flex:1;font-size:12px;padding:8px;font-family:monospace" '
        'onkeydown="if(event.key===\'Enter\')execShell()">'
        '<button onclick="execShell()" style="font-size:11px;padding:8px 14px;white-space:nowrap">▶ 执行</button></div>'
        '<div style="display:flex;gap:4px;margin-top:4px;flex-wrap:wrap">'
        '<button onclick="quickExec(\'git status\')" class="lc-tool-btn">git status</button>'
        '<button onclick="quickExec(\'python --version\')" class="lc-tool-btn">python --version</button>'
        '<button onclick="quickExec(\'pip list\')" class="lc-tool-btn">pip list</button>'
        '<button onclick="quickExec(\'dir\')" class="lc-tool-btn">dir</button>'
        '<button onclick="quickExec(\'node --version\')" class="lc-tool-btn">node --version</button></div>'
        '<div id="shell-output" style="margin-top:8px"></div>'
        '<div id="shell-env" hx-get="/tree/shell/env" hx-trigger="revealed" hx-swap="innerHTML" style="margin-top:12px"></div></div>')


__all__ = ["shell_router"]
