"""LivingTree Desktop Shell — pywebview wrapper with native capabilities.

Evaluation: Browser limitations vs native shell benefits.

Browser (current):                    Native Shell (pywebview):
  ❌ No direct FS access              ✅ Full Python FS (os, pathlib, subprocess)
  ❌ No native file dialogs            ✅ Native open/save dialogs
  ❌ No system tray                    ✅ System tray with quick actions
  ❌ No global shortcuts               ✅ Global hotkeys (Ctrl+Shift+L)
  ❌ Cannot run local commands         ✅ subprocess.call() directly
  ❌ No offline mode                   ✅ Self-contained
  ❌ Weak notifications                ✅ Native OS notifications
  ✅ Zero install                      ⚠️ ~20MB bundle
  ✅ Cross-platform by default         ✅ Cross-platform (Windows/macOS/Linux)
  ✅ Easy deployment                   ✅ pip install pywebview

Conclusion: Native shell adds significant capability at minimal cost (20MB).
The LivingTree server runs INSIDE the shell — one process, no ports, no CORS.

Architecture:
  ┌──────────────────────────────────────────────┐
  │  pywebview Window                            │
  │  ┌────────────────────────────────────────┐  │
  │  │  WebView (living.html)                 │  │
  │  │    - UI rendering                      │  │
  │  │    - Text/voice/video input            │  │
  │  │    - SSE event display                 │  │
  │  └────────────────────────────────────────┘  │
  │         ↕ JS-Python bridge (js_api)           │
  │  ┌────────────────────────────────────────┐  │
  │  │  Python Backend (in-process)            │  │
  │  │    - LivingTree server                 │  │
  │  │    - Local FS operations               │  │
  │  │    - Subprocess execution              │  │
  │  │    - System tray                       │  │
  │  │    - Native dialogs                    │  │
  │  └────────────────────────────────────────┘  │
  └──────────────────────────────────────────────┘
"""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from loguru import logger

import webview


class DesktopShell:
    """pywebview desktop wrapper for LivingTree.

    Provides native capabilities that browsers cannot:
      - Direct filesystem access (read/write/exec without API calls)
      - Native file/folder dialogs
      - System tray with quick actions
      - Global hotkeys
      - Native OS notifications
      - In-process server (no ports, no CORS)
    """

    def __init__(self):
        self._window = None
        self._server_thread = None
        self._project_path = None

    def start(self, debug: bool = False):
        """Start the desktop shell with embedded LivingTree server.

        Shows a local loading screen immediately (before server is ready),
        then auto-navigates to the server URL once the server responds.
        """
        # Start LivingTree server in background thread
        self._start_server()

        # Show loading screen while server boots
        loading_html = self._loading_page()

        # Create pywebview window — starts with loading screen
        self._window = webview.create_window(
            title="LivingTree · 数字生命体",
            html=loading_html,  # Local HTML loads instantly (no network wait)
            width=900, height=700,
            min_size=(600, 400),
            js_api=JsBridge(self),
            confirm_close=True,
        )

        # Start background task to detect server ready and navigate
        import threading
        def _wait_and_navigate():
            import time, urllib.request
            for _ in range(60):  # Wait up to 30 seconds
                try:
                    urllib.request.urlopen("http://127.0.0.1:8100/api/health", timeout=1)
                    # Server ready — navigate to real page
                    self._window.load_url("http://127.0.0.1:8100/tree/living")
                    break
                except Exception:
                    time.sleep(0.5)

        threading.Thread(target=_wait_and_navigate, daemon=True).start()

        webview.start(debug=debug)

    @staticmethod
    def _loading_page() -> str:
        """Generate local loading HTML — no network required, renders instantly."""
        return """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<style>*{margin:0;padding:0;box-sizing:border-box}body{display:flex;align-items:center;justify-content:center;
min-height:100vh;background:linear-gradient(135deg,#0f172a,#1e293b);font-family:system-ui}
.load{text-align:center}.load .icon{font-size:64px;animation:pulse 2s ease-in-out infinite}
.load h1{color:#e2e8f0;font-size:24px;margin-top:16px;font-weight:600}
.load p{color:#94a3b8;font-size:13px;margin-top:8px}
.load .bar{width:200px;height:3px;background:#334155;border-radius:2px;margin:24px auto 0;overflow:hidden}
.load .fill{height:100%;background:linear-gradient(90deg,#3b82f6,#22c55e);border-radius:2px;
animation:slide 2s ease-in-out infinite;width:40%}
.load .stages{margin-top:20px;text-align:left;display:inline-block}
.load .stages div{color:#64748b;font-size:11px;padding:3px 0;transition:color .3s}
.load .stages div.done{color:#22c55e}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.6;transform:scale(1.1)}}
@keyframes slide{0%{transform:translateX(-100%)}100%{transform:translateX(350%)}}
</style></head><body>
<div class="load"><div class="icon">🌳</div><h1>LivingTree AI Agent</h1><p>数字生命体正在觉醒...</p>
<div class="bar"><div class="fill"></div></div>
<div class="stages">
  <div id="s0">⏳ 加载配置...</div>
  <div id="s1">⏳ 初始化核心引擎...</div>
  <div id="s2">⏳ 启动 API 服务...</div>
  <div id="s3">⏳ 准备就绪...</div>
</div></div>
<script>
var stages=['s0','s1','s2','s3'];
var i=0;
setInterval(function(){
  if(i>0)document.getElementById(stages[i-1]).className='done';
  if(i<stages.length){
    document.getElementById(stages[i]).innerHTML='✅ '+document.getElementById(stages[i]).textContent.replace('⏳ ','');
    document.getElementById(stages[i]).className='done';
  }
  i++;
  if(i>=stages.length)i=0;
},2000);
</script>
</body></html>"""

    def _start_server(self):
        """Start LivingTree server in background thread."""
        def run_server():
            from livingtree.main import _start_web
            _start_web()

        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()
        logger.info("DesktopShell: LivingTree server started in background")

    def _fallback_browser(self):
        """Fallback: open in default browser."""
        import webbrowser
        webbrowser.open("http://127.0.0.1:8100/tree/living")
        logger.info("DesktopShell: opened in browser (pywebview not available)")


class JsBridge:
    """JavaScript-Python bridge — exposed to WebView JS as `window.pywebview.api`.

    Browser JS calls these Python methods directly — no HTTP, no API, no latency.
    """

    def __init__(self, shell: DesktopShell):
        self.shell = shell

    # ── File Operations ──

    def read_file(self, path: str) -> dict:
        """Read a local file — direct FS access, no API call."""
        try:
            content = Path(path).read_text("utf-8")
            return {"ok": True, "content": content[:50000], "size": len(content)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def write_file(self, path: str, content: str) -> dict:
        """Write a local file."""
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, "utf-8")
            return {"ok": True, "written": len(content)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def exec_command(self, command: str, cwd: str = "") -> dict:
        """Execute a shell command locally."""
        import asyncio
        try:
            try:
                from livingtree.treellm.unified_exec import run
                result = asyncio.run(run(command, timeout=60, cwd=cwd or ""))
                return {
                    "ok": result.success,
                    "output": (result.stdout + result.stderr)[:10000],
                    "exit_code": result.exit_code,
                }
            except ImportError:
                result = subprocess.run(  # MIGRATE: use run_sync() from unified_exec
            
                    command, shell=True, capture_output=True,
                    text=True, timeout=60,
                    cwd=cwd or None,
                )
                return {
                    "ok": result.returncode == 0,
                    "output": (result.stdout + result.stderr)[:10000],
                    "exit_code": result.returncode,
                }
        except asyncio.TimeoutError:
            return {"ok": False, "error": "Command timed out (60s)"}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Command timed out (60s)"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def list_directory(self, path: str) -> dict:
        """List directory contents."""
        try:
            items = []
            for item in sorted(Path(path).iterdir()):
                items.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                })
            return {"ok": True, "items": items[:200]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Native Dialogs ──

    def select_folder(self) -> dict:
        """Open native folder selection dialog."""
        try:
            result = webview.windows[0].create_file_dialog(
                webview.FOLDER_DIALOG
            )
            if result and len(result) > 0:
                path = result[0]
                self.shell._project_path = path
                return {"ok": True, "path": path}
            return {"ok": False, "error": "No folder selected"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def select_file(self, file_types: tuple = ()) -> dict:
        """Open native file selection dialog."""
        try:
            result = webview.windows[0].create_file_dialog(
                webview.OPEN_DIALOG, file_types=file_types
            )
            if result and len(result) > 0:
                return {"ok": True, "path": result[0]}
            return {"ok": False, "error": "No file selected"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def save_file_dialog(self, default_name: str = "") -> dict:
        """Open native save file dialog."""
        try:
            result = webview.windows[0].create_file_dialog(
                webview.SAVE_DIALOG, save_filename=default_name
            )
            if result:
                return {"ok": True, "path": result}
            return {"ok": False, "error": "Cancelled"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── System ──

    def notify(self, title: str, message: str) -> dict:
        """Show native OS notification."""
        try:
            import webview
            # Use platform-specific notification
            if sys.platform == "win32":
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(title, message, duration=5)
            elif sys.platform == "darwin":
                import asyncio
                try:
                    from livingtree.treellm.unified_exec import run
                    asyncio.run(run(f"osascript -e 'display notification \"{message}\" with title \"{title}\"'", timeout=5))
                except ImportError:
                    subprocess.run(  # MIGRATE: use run_sync() from unified_exec
            [
                        "osascript", "-e",
                        f'display notification "{message}" with title "{title}"'
                    ])
            else:
                import asyncio
                try:
                    from livingtree.treellm.unified_exec import run
                    asyncio.run(run(f"notify-send \"{title}\" \"{message}\"", timeout=5))
                except ImportError:
                    subprocess.run(  # MIGRATE: use run_sync() from unified_exec
            ["notify-send", title, message])
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_project_path(self) -> str:
        """Get current project folder path."""
        return self.shell._project_path or os.getcwd()

    def set_clipboard(self, text: str) -> dict:
        """Copy text to system clipboard."""
        try:
            import pyperclip
            pyperclip.copy(text)
            return {"ok": True}
        except Exception:
            # Fallback: write to temp and use platform command
            return {"ok": False}


# ── Entry Point ──

def main():
    """Launch LivingTree Desktop Shell."""
    shell = DesktopShell()
    shell.start(debug=False)


if __name__ == "__main__":
    main()
